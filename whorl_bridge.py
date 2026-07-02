#!/usr/bin/env python3
"""
whorl_bridge.py
───────────────
HTTP bridge between the Vertical AI Boardroom frontend and the Whorl workbench.

Exposes the boardroom-compatible contract the frontend already expects, while
routing every request through Whorl modules (hotseat, forge, tailor, scouts).
Whorl handles multi-provider LLM fallback (OpenAI → Groq → Mistral → Gemini
→ Ollama) via vault.load_api_keys() — no hardcoded keys here.

Usage:
    python whorl_bridge.py [--port 8767] [--host 127.0.0.1]

Endpoints:
    GET  /status            — liveness + Whorl module inventory
    POST /convene           — run a full boardroom session via Hotseat
    POST /forge             — generate a vertical pitch
    POST /tailor/qrd        — QRD tiered summary
    POST /tailor/intent     — parse a raw thought into a structured plan
    GET  /scouts            — return recent scout signals
    GET  /bearings          — return agent Bearing vectors
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

# ── Make sure Whorl is importable from local clone or installed package ──────
_WHORL_REPO = Path(__file__).parent.parent / "Whorl"
if (_WHORL_REPO / "whorl").is_dir() and str(_WHORL_REPO) not in sys.path:
    sys.path.insert(0, str(_WHORL_REPO))

# ── Whorl module availability map (gracefully degrade when unavailable) ──────
_WHORL_OK: Dict[str, bool] = {}


def _try_import(name: str):
    try:
        mod = __import__(name, fromlist=["_"])
        _WHORL_OK[name] = True
        return mod
    except Exception as exc:
        _WHORL_OK[name] = False
        print(f"[whorl_bridge] WARNING: could not import {name}: {exc}")
        return None


# Pre-import all modules at startup for faster request handling
_hotseat = _try_import("whorl.hotseat")
_forge   = _try_import("whorl.forge")
_tailor  = _try_import("whorl.tailor")
_scouts  = _try_import("whorl.scouts")
_models  = _try_import("whorl.core.models")
_db      = _try_import("whorl.core.db")
_cfg_mod = _try_import("whorl.core.config")

# Run DB migrations once at startup
if _db:
    try:
        _db.migrate()
        print("[whorl_bridge] DB migrations applied.")
    except Exception as e:
        print(f"[whorl_bridge] DB migration warning: {e}")


# ── Bearing config for each boardroom agent ───────────────────────────────────
# Maps agent id → Bearing(x, y, z, cw, ccw)
#   x:  0=local  1=regional  2=national  3=global
#   y:  0=surface  1=analysis  2=synthesis  3=strategy
#   z:  0=read-only  1=draft  2=send  3=deploy
#   cw: can escalate   ccw: can delegate
AGENT_BEARINGS: Dict[str, Dict[str, Any]] = {
    "cfo":   {"x": 2, "y": 3, "z": 1, "cw": True,  "ccw": False,
              "label": "CFO",     "desc": "Capital scope: national | Depth: strategy | Exec: draft"},
    "cmo":   {"x": 3, "y": 2, "z": 2, "cw": False, "ccw": True,
              "label": "CMO",     "desc": "Lateral scope: global | Depth: synthesis | Exec: send"},
    "cro":   {"x": 1, "y": 2, "z": 1, "cw": True,  "ccw": False,
              "label": "CRO",     "desc": "Lateral scope: regional | Depth: synthesis | Exec: draft"},
    "mkt":   {"x": 2, "y": 1, "z": 0, "cw": False, "ccw": False,
              "label": "ANALYST", "desc": "Lateral scope: national | Depth: analysis | Exec: read-only"},
    "devil": {"x": 3, "y": 3, "z": 2, "cw": True,  "ccw": True,
              "label": "DEVIL",   "desc": "Lateral scope: global | Depth: strategy | Exec: send | Full delegate"},
}


# ── Response helpers ──────────────────────────────────────────────────────────

def _json_response(handler: BaseHTTPRequestHandler,
                   data: Any, status: int = 200) -> None:
    body = json.dumps(data, default=str).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.end_headers()
    handler.wfile.write(body)


def _read_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", 0))
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw)
    except Exception:
        return {}


# ── Hotseat → boardroom format adapter ───────────────────────────────────────

def _map_hotseat_to_boardroom(session, brief: str, agent_map: Dict[str, str]) -> dict:
    """
    Convert a HotseatSession (audrey, claib, vertical) into the
    {boardroom: {debate, synthesis}, champion} shape the frontend expects.

    We spread the three Hotseat voices across the five boardroom agents,
    preserving the actual LLM output so the room feels real.
    """
    debate = []

    # Audrey → CFO + CRO  (auditor energy, critical)
    if session.audrey:
        chunks = _split_voice(session.audrey)
        if len(chunks) >= 1:
            debate.append({"agent": agent_map.get("audrey_cfo", "CFO"),   "argument": chunks[0]})
        if len(chunks) >= 2:
            debate.append({"agent": agent_map.get("audrey_cro", "CRO"),   "argument": chunks[1]})

    # Claib → CMO + DEVIL  (optimist / wildcard energy)
    if session.claib:
        chunks = _split_voice(session.claib)
        if len(chunks) >= 1:
            debate.append({"agent": agent_map.get("claib_cmo", "CMO"),    "argument": chunks[0]})
        if len(chunks) >= 2:
            debate.append({"agent": agent_map.get("claib_devil", "DEVIL"),"argument": chunks[1]})

    # Vertical AI → ANALYST + synthesis verdict
    if session.vertical:
        chunks = _split_voice(session.vertical)
        debate.append({"agent": agent_map.get("vertical_analyst", "ANALYST"), "argument": chunks[0]})

    # Parse Vertical AI's verdict token (GO / NO-GO / PIVOT / CONDITIONAL)
    verdict_raw = (session.vertical or "").upper()
    if "NO-GO" in verdict_raw or "NO GO" in verdict_raw:
        verdict = "no-go"
    elif verdict_raw.strip().startswith("GO") or " GO." in verdict_raw or " GO," in verdict_raw:
        verdict = "go"
    elif "PIVOT" in verdict_raw:
        verdict = "conditional"
    else:
        verdict = "conditional"

    # Build synthesis
    synthesis = {
        "verdict":   verdict,
        "consensus": session.vertical or "Board has deliberated.",
        "hotseat_id": session.id,
    }

    # Champion = whoever had the loudest signal (most words from Claib if go, Audrey if no-go)
    champion_name = "CMO" if verdict == "go" else "CFO" if verdict == "no-go" else "ANALYST"
    champion_text = session.claib if verdict == "go" else session.audrey

    champion = {
        "name":   champion_name,
        "thesis": (champion_text or "")[:120],
    }

    return {
        "boardroom": {"debate": debate, "synthesis": synthesis},
        "champion":  champion,
        "session_id": session.id,
    }


def _split_voice(text: str, max_chunks: int = 2) -> list:
    """
    Split a voice response into at most max_chunks pieces
    so we can assign them to different agents.
    Uses paragraph boundaries if available, otherwise mid-split.
    """
    text = text.strip()
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paras) >= 2:
        return paras[:max_chunks]
    # Try sentence split at midpoint
    sentences = [s.strip() + "." for s in text.rstrip(".").split(". ") if s.strip()]
    if len(sentences) >= 4:
        mid = len(sentences) // 2
        return [" ".join(sentences[:mid]), " ".join(sentences[mid:])]
    return [text]


# ── Simulation fallback (no LLM) ─────────────────────────────────────────────

def _sim_boardroom(brief: str) -> dict:
    """Return a canned boardroom response so the bridge is always live."""
    import random
    agents = ["CFO", "CMO", "CRO", "ANALYST", "DEVIL"]
    lines = {
        "CFO":    f"[CFO] The unit economics here need scrutiny. What's the CAC and payback period for: {brief[:60]}?",
        "CMO":    "[CMO] Nobody here has talked to a customer yet. One real conversation before we model anything.",
        "CRO":    "[CRO] I found the kill shot. Single supplier dependency is the landmine on month four.",
        "ANALYST":"[ANALYST] Comparable exits in this vertical: 2-3x revenue. The 10x model is fiction.",
        "DEVIL":  "[DEVIL] The CFO's argument is strongest — and I'm about to destroy it. Network effects break the math.",
    }
    debate = [{"agent": a, "argument": lines[a]} for a in agents]
    verdicts = ["go", "no-go", "conditional"]
    v = random.choice(verdicts)
    return {
        "boardroom": {
            "debate": debate,
            "synthesis": {
                "verdict": v,
                "consensus": "Simulation mode — start Whorl + Ollama for live deliberation.",
                "hotseat_id": None,
            }
        },
        "champion": {"name": "ANALYST", "thesis": "Data first, always."},
        "session_id": "sim_" + str(uuid.uuid4())[:8],
    }


# ── Request handler ───────────────────────────────────────────────────────────

class BoardroomHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        # Quiet noisy access log; only print errors
        if args and str(args[1]) not in ("200", "204"):
            super().log_message(fmt, *args)

    # ── CORS preflight ────────────────────────────────────────────────────────
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    # ── GET ───────────────────────────────────────────────────────────────────
    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/")

        if path == "/status":
            self._handle_status()
        elif path == "/scouts":
            self._handle_scouts()
        elif path == "/bearings":
            self._handle_bearings()
        else:
            _json_response(self, {"error": "not found"}, 404)

    # ── POST ──────────────────────────────────────────────────────────────────
    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/")

        if path == "/convene":
            self._handle_convene()
        elif path == "/forge":
            self._handle_forge()
        elif path == "/tailor/qrd":
            self._handle_tailor_qrd()
        elif path == "/tailor/intent":
            self._handle_tailor_intent()
        elif path == "/scouts/ingest":
            self._handle_scouts_ingest()
        else:
            _json_response(self, {"error": "not found"}, 404)

    # ── /status ───────────────────────────────────────────────────────────────
    def _handle_status(self):
        modules = {
            "hotseat": _WHORL_OK.get("whorl.hotseat", False),
            "forge":   _WHORL_OK.get("whorl.forge",   False),
            "tailor":  _WHORL_OK.get("whorl.tailor",  False),
            "scouts":  _WHORL_OK.get("whorl.scouts",  False),
            "db":      _WHORL_OK.get("whorl.core.db", False),
        }
        db_counts = {}
        if _db and _WHORL_OK.get("whorl.core.db"):
            for t in ["signals", "pitches", "hotseat_sessions", "qrds", "agents"]:
                try:
                    db_counts[t] = _db.count(t)
                except Exception:
                    db_counts[t] = -1

        _json_response(self, {
            "status":    "online",
            "version":   "whorl_bridge 1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "whorl_path": str(_WHORL_REPO),
            "modules":   modules,
            "db":        db_counts,
            "bearings":  AGENT_BEARINGS,
        })

    # ── /convene ──────────────────────────────────────────────────────────────
    def _handle_convene(self):
        body  = _read_body(self)
        brief = body.get("brief", "").strip()

        if not brief:
            _json_response(self, {"error": "brief is required"}, 400)
            return

        # Tailor: pre-process the brief through intent parser for richer context
        enriched_brief = brief
        if _tailor and _WHORL_OK.get("whorl.tailor"):
            try:
                intent = _tailor.parse_intent(brief)
                domain = intent.get("domain_hint", "")
                core   = intent.get("core_intent", "")
                if core and core.lower() != brief.lower():
                    enriched_brief = f"{brief}\n\n[TAILOR CONTEXT: domain={domain}, intent={core}]"
            except Exception as e:
                print(f"[whorl_bridge] Tailor intent pre-processing skipped: {e}")

        # Run Hotseat
        if _hotseat and _WHORL_OK.get("whorl.hotseat"):
            try:
                session = _hotseat.run(enriched_brief, silent=True)
                agent_map = {
                    "audrey_cfo":       "CFO",
                    "audrey_cro":       "CRO",
                    "claib_cmo":        "CMO",
                    "claib_devil":      "DEVIL",
                    "vertical_analyst": "ANALYST",
                }
                result = _map_hotseat_to_boardroom(session, brief, agent_map)
                _json_response(self, result)
                return
            except Exception as e:
                print(f"[whorl_bridge] Hotseat error: {e}")
                traceback.print_exc()
                # Fall through to simulation

        # Simulation fallback
        _json_response(self, _sim_boardroom(brief))

    # ── /forge ────────────────────────────────────────────────────────────────
    def _handle_forge(self):
        body     = _read_body(self)
        target   = body.get("target", "").strip()
        vertical = body.get("vertical", "general").strip().lower()
        signal   = body.get("signal_context", "")
        extra    = body.get("extra_context", "")

        if not target:
            _json_response(self, {"error": "target is required"}, 400)
            return

        if not (_forge and _WHORL_OK.get("whorl.forge")):
            _json_response(self, {"error": "forge module unavailable"}, 503)
            return

        try:
            vert_enum = _models.Vertical(vertical)
        except (ValueError, AttributeError):
            vert_enum = _models.Vertical.GENERAL if _models else None

        if vert_enum is None:
            _json_response(self, {"error": "models module unavailable"}, 503)
            return

        try:
            pitch = _forge.generate(
                target=target, vertical=vert_enum,
                signal_context=signal, extra_context=extra
            )
            _json_response(self, {
                "id":        pitch.id,
                "target":    pitch.target,
                "vertical":  pitch.vertical.value,
                "hook":      pitch.hook,
                "situation": pitch.situation,
                "risk":      pitch.risk,
                "fix":       pitch.fix,
                "ask":       pitch.ask,
                "cost":      pitch.cost,
                "guarantee": pitch.guarantee,
            })
        except Exception as e:
            traceback.print_exc()
            _json_response(self, {"error": str(e)}, 500)

    # ── /tailor/qrd ───────────────────────────────────────────────────────────
    def _handle_tailor_qrd(self):
        body = _read_body(self)
        text = body.get("text", "").strip()

        if not text:
            _json_response(self, {"error": "text is required"}, 400)
            return

        if not (_tailor and _WHORL_OK.get("whorl.tailor")):
            _json_response(self, {"error": "tailor module unavailable"}, 503)
            return

        try:
            record = _tailor.qrd(text, source_id=body.get("source_id", "boardroom"))
            _json_response(self, {
                "id":    record.id,
                "blink": record.blink,
                "brief": record.brief,
                "deep":  record.deep,
            })
        except Exception as e:
            traceback.print_exc()
            _json_response(self, {"error": str(e)}, 500)

    # ── /tailor/intent ────────────────────────────────────────────────────────
    def _handle_tailor_intent(self):
        body    = _read_body(self)
        thought = body.get("thought", "").strip()

        if not thought:
            _json_response(self, {"error": "thought is required"}, 400)
            return

        if not (_tailor and _WHORL_OK.get("whorl.tailor")):
            _json_response(self, {"error": "tailor module unavailable"}, 503)
            return

        try:
            result = _tailor.parse_intent(thought)
            _json_response(self, result)
        except Exception as e:
            traceback.print_exc()
            _json_response(self, {"error": str(e)}, 500)

    # ── /scouts ───────────────────────────────────────────────────────────────
    def _handle_scouts(self):
        limit = 20
        if not (_scouts and _WHORL_OK.get("whorl.scouts")):
            _json_response(self, {"signals": [], "error": "scouts module unavailable"})
            return
        try:
            rows = _scouts.list_signals(limit=limit)
            _json_response(self, {"signals": rows})
        except Exception as e:
            _json_response(self, {"signals": [], "error": str(e)})

    # ── /scouts/ingest ────────────────────────────────────────────────────────
    def _handle_scouts_ingest(self):
        body = _read_body(self)
        raw  = body.get("raw", "").strip()
        if not raw:
            _json_response(self, {"error": "raw is required"}, 400)
            return

        if not (_scouts and _WHORL_OK.get("whorl.scouts")):
            _json_response(self, {"error": "scouts module unavailable"}, 503)
            return
        try:
            signals = _scouts.ingest_text(raw)
            _json_response(self, {"ingested": len(signals),
                                   "signals": [{"id": s.id, "headline": s.headline}
                                               for s in signals]})
        except Exception as e:
            traceback.print_exc()
            _json_response(self, {"error": str(e)}, 500)

    # ── /bearings ─────────────────────────────────────────────────────────────
    def _handle_bearings(self):
        _json_response(self, {"bearings": AGENT_BEARINGS})


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Whorl → Boardroom HTTP bridge")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()

    print(f"""
 ██╗    ██╗██╗  ██╗ ██████╗ ██████╗ ██╗
 ██║    ██║██║  ██║██╔═══██╗██╔══██╗██║
 ██║ █╗ ██║███████║██║   ██║██████╔╝██║
 ██║███╗██║██╔══██║██║   ██║██╔══██╗██║
 ╚███╔███╔╝██║  ██║╚██████╔╝██║  ██║███████╗
  ╚══╝╚══╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝
  Boardroom Bridge — http://{args.host}:{args.port}
""")

    print("[whorl_bridge] Module status:")
    for name, ok in _WHORL_OK.items():
        status = "OK" if ok else "UNAVAILABLE"
        print(f"  {name:<30} {status}")

    print(f"\n[whorl_bridge] Listening on http://{args.host}:{args.port}")
    print("[whorl_bridge] Open vertical_ai_boardroom_3d.html and click PING BRIDGE\n")

    server = HTTPServer((args.host, args.port), BoardroomHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[whorl_bridge] Shutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
