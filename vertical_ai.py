#!/usr/bin/env python3
"""
VERTICAL AI -- Conductor
Universal input -> Boardroom -> Fractal Sim -> Genetic Arena -> Champion

Usage:
  python vertical_ai.py --text "your idea"
  python vertical_ai.py --file path/to/doc.txt
  python vertical_ai.py --url https://example.com
  python vertical_ai.py --scrape scouts/output.json
  python vertical_ai.py --session SESSION_ID
  python vertical_ai.py --list
  echo "idea" | python vertical_ai.py

Flags:
  --tracks N       simulation tracks (default 3)
  --iterations N   fractal iterations per track (default 4)
  --rounds N       boardroom rounds (default 2)
  --generations N  genetic generations (default 2)
  --outreach       generate outreach payload
  --no-neo4j       skip persistence
"""

import sys, os, json, argparse, hashlib
from datetime import datetime


def load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if not os.environ.get(k.strip()):
                        os.environ[k.strip()] = v.strip()
load_env()

from router import check_providers, ModelTier, call_model
from boardroom import run_boardroom
from simulator import run_fractal_simulation
from genetics import run_arena
from state import save_run, load_session, list_sessions


def normalize_input(args):
    context = {"timestamp": datetime.now().isoformat(), "raw": None, "type": None, "label": None, "data": {}}

    if args.text:
        context.update({"type":"text","raw":args.text,"label":args.text[:60],"data":{"content":args.text}})
    elif args.file:
        if not os.path.exists(args.file):
            print(f"File not found: {args.file}"); sys.exit(1)
        content = open(args.file,"r",errors="replace").read()
        context.update({"type":"document","raw":content,"label":os.path.basename(args.file),"data":{"content":content}})
    elif args.url:
        import urllib.request
        print(f"  Fetching {args.url}...", end="", flush=True)
        try:
            with urllib.request.urlopen(args.url, timeout=15) as r:
                content = r.read().decode("utf-8",errors="replace")[:8000]
            print(" done")
        except Exception as e:
            print(f"\n  Fetch failed: {e}"); sys.exit(1)
        context.update({"type":"url","raw":content,"label":args.url,"data":{"url":args.url,"content":content}})
    elif args.json_input:
        try:
            data = json.loads(args.json_input)
        except Exception as e:
            print(f"Invalid JSON: {e}"); sys.exit(1)
        context.update({"type":"json","raw":args.json_input,"label":str(data)[:60],"data":data})
    elif args.scrape:
        if not os.path.exists(args.scrape):
            print(f"File not found: {args.scrape}"); sys.exit(1)
        data = json.load(open(args.scrape))
        label = f"{len(data)} targets" if isinstance(data,list) else data.get("name","scrape")
        context.update({"type":"scrape","raw":json.dumps(data),"label":label,"data":data})
    elif not sys.stdin.isatty():
        content = sys.stdin.read().strip()
        context.update({"type":"stdin","raw":content,"label":content[:60],"data":{"content":content}})
    else:
        return None

    h = hashlib.md5((context["raw"]+context["timestamp"]).encode()).hexdigest()[:12]
    context["session_id"] = f"vai_{h}"
    return context


def generate_outreach(champion, context):
    print("\n-- OUTREACH PAYLOAD --")
    print("  Generating...", end="", flush=True)
    prompt = f"""
CHAMPION: {json.dumps(champion, indent=2)}
CONTEXT: {json.dumps(context.get('data',{}))[:2000]}

Outreach payload ready for AI agents. Real hooks. Real copy.

JSON only:
{{"subject_line":"","hook":"","value_proposition":"","pain_point_addressed":"","call_to_action":"","tone":"consultative","platform_variants":{{"email":"","linkedin":"","sms":""}},"objection_handlers":{{"no budget":"","not interested":"","already have someone":""}}}}
"""
    try:
        raw, provider = call_model(prompt, tier=ModelTier.FAST)
        print(f" ({provider})")
        return json.loads(raw.strip().replace("```json","").replace("```","").strip())
    except Exception as e:
        print(f"\n  Failed: {e}")
        return {"error": str(e)}


def print_champion(champion, session_id):
    print(f"\n{'='*60}")
    print("  VERTICAL AI -- CHAMPION STRATEGY")
    print(f"{'='*60}")
    print(f"  Session:  {session_id}")
    print(f"  Name:     {champion.get('name','')}")
    print(f"  Thesis:   {champion.get('thesis','')}")
    print(f"  Action:   {champion.get('first_action','')}")
    print(f"  Mutation: {champion.get('mutation','')}")
    print(f"  From A:   {champion.get('inherited_from_a','')}")
    print(f"  From B:   {champion.get('inherited_from_b','')}")
    print(f"  Outcome:  {champion.get('target_outcome','')}")
    print(f"{'='*60}")
    print(f"  Handoff: python vertical_ai.py --session {session_id}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="VERTICAL AI -- Strategic Decision Engine")
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--text")
    g.add_argument("--file")
    g.add_argument("--url")
    g.add_argument("--json-input")
    g.add_argument("--scrape")
    g.add_argument("--session")
    g.add_argument("--list", action="store_true")
    parser.add_argument("--tracks", type=int, default=3)
    parser.add_argument("--iterations", type=int, default=4)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--generations", type=int, default=2)
    parser.add_argument("--outreach", action="store_true")
    parser.add_argument("--vertical", default=None, help="Industry vertical for Firefly scout")
    parser.add_argument("--deep-scout", action="store_true", help="Pull live govt data")
    parser.add_argument("--no-neo4j", action="store_true")
    args = parser.parse_args()

    if args.list:
        sessions = list_sessions(20)
        if not sessions:
            print("No sessions found."); return
        print(f"\n{'='*60}\n  RECENT SESSIONS\n{'='*60}")
        for s in sessions:
            print(f"  {s.get('id')} | {str(s.get('ts',''))[:19]} | {s.get('label','')[:30]} | {s.get('verdict','?')} | {s.get('champion','none')}")
        return

    if args.session:
        data = load_session(args.session)
        if not data:
            print(f"Session not found: {args.session}"); sys.exit(1)
        print(f"\nHANDOFF -- {args.session}")
        print(json.dumps(data, indent=2)); return

    print("\n  Checking providers...", end="", flush=True)
    providers = check_providers()
    active = []
    if providers.get("gemini"): active.append("Gemini(Chairman)")
    if providers.get("groq"): active.append("Groq(Boardroom)")
    if providers.get("ollama"): active.append(f"Ollama({len(providers['ollama'])} models)")
    if not active:
        print("\n  No providers available. Set GEMINI_API_KEY or GROQ_API_KEY."); sys.exit(1)
    print(f" {' | '.join(active)}\n")

    context = normalize_input(args)

    # Auto-scout vertical context
    if context and args.vertical:
        try:
            sys.path.insert(0, os.path.dirname(__file__))
            from firefly_lite import build_vertical_context
            vfile, vcontent = build_vertical_context(args.vertical, deep=args.deep_scout)
            context["data"]["content"] = vcontent + "\n\n" + context["data"].get("content","")
        except Exception as e:
            print(f"  [Firefly] Scout failed: {e}")
    if not context:
        parser.print_help(); sys.exit(0)

    print(f"  Input:   [{context['type']}] {context['label']}")
    print(f"  Session: {context['session_id']}\n")

    boardroom_result = run_boardroom(context, rounds=args.rounds)

    verdict = boardroom_result.get("synthesis",{}).get("verdict","unknown")
    if verdict == "no-go":
        print(f"\n  BOARDROOM VERDICT: NO-GO")
        print(f"  {boardroom_result['synthesis'].get('primary_risk','')}")
        sys.exit(0)

    simulated = run_fractal_simulation(boardroom_result["synthesis"], context,
                                        tracks=args.tracks, iterations=args.iterations)
    if not simulated:
        print("Simulation failed."); sys.exit(1)

    arena = run_arena(simulated, context, generations=args.generations)
    champion = arena.get("champion",{})
    print_champion(champion, context["session_id"])

    outreach = None
    if args.outreach:
        outreach = generate_outreach(champion, context)
        print(json.dumps(outreach, indent=2))

    if not args.no_neo4j:
        print("  Saving to Neo4j...", end="", flush=True)
        saved = save_run(context["session_id"], context, boardroom_result, simulated, arena)
        if saved: print(" done")

    out_file = f"vai_output_{context['session_id']}.json"
    full = {"session_id": context["session_id"], "context": context,
            "boardroom": boardroom_result, "tracks": simulated,
            "arena": arena, "champion": champion}
    if outreach: full["outreach"] = outreach
    json.dump(full, open(out_file,"w"), indent=2, default=str)
    print(f"  Output: {out_file}\n")

if __name__ == "__main__":
    main()
