#!/usr/bin/env python3
"""
VERTICAL AI -- Swarm Intelligence
Scout layer. Real intel. Feeds conductor.
Usage:
  python swarm_intel.py --target "Wells Fargo"
  python swarm_intel.py --target "Mikes Plumbing" --location "Phoenix AZ" --pipe
  python swarm_intel.py --batch targets.txt
"""

import sys, os, json, argparse, subprocess
from datetime import datetime

_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_dir)
sys.path.insert(0, _root)
sys.path.insert(0, _dir)

from cfpb import get_complaint_summary
from web_search import get_business_signals

try:
    from router import call_model, ModelTier
    ROUTER_AVAILABLE = True
except ImportError:
    ROUTER_AVAILABLE = False


def load_env():
    env_path = os.path.join(_root, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if not os.environ.get(k.strip()):
                        os.environ[k.strip()] = v.strip()
load_env()


def synthesize(target_name, cfpb_data, web_data):
    # Try calling the model first if keys are available
    has_keys = os.environ.get("GEMINI_API_KEY") or os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if ROUTER_AVAILABLE and has_keys:
        prompt = f"""
TARGET: {target_name}
CFPB: {json.dumps(cfpb_data)[:1500]}
WEB: {json.dumps(web_data)[:1500]}

Sharp corporate intelligence briefing. Specific. Reference actual data.
1. RISK PROFILE
2. OPPORTUNITY SIGNAL
3. RECOMMENDED ANGLE
4. CONFIDENCE (high/medium/low and why)
"""
        try:
            result, provider = call_model(prompt, tier=ModelTier.FAST)
            return f"[{provider}]\n\n{result.strip()}"
        except Exception:
            pass

    # Dynamic Rule-Based Local Synthesis Fallback
    lines = [
        f"=== LOCAL SCOUT BRIEFING FOR {target_name.upper()} ===",
        f"CFPB Complaints: {cfpb_data.get('complaint_count', 0)} recent reports."
    ]
    if cfpb_data.get("complaint_count", 0) > 0:
        lines.append("\n1. RISK PROFILE:")
        lines.append(f"   - Active CFPB footprint with {cfpb_data.get('complaint_count')} complaints.")
        for flag in cfpb_data.get("risk_flags", []):
            lines.append(f"   - FLAG: {flag}")
    else:
        lines.append("\n1. RISK PROFILE:")
        lines.append("   - Clean CFPB record. No consumer regulatory complaints detected.")

    lines.append("\n2. OPPORTUNITY SIGNAL:")
    web_results = web_data.get("results", [])
    if web_results:
        lines.append(f"   - Found {len(web_results)} relevant web search results.")
        for flag in web_data.get("opportunity_flags", []):
            lines.append(f"   - {flag}")
    else:
        lines.append("   - No active web presence / social signals detected in basic sweep.")
        lines.append("   - High-value target for a digital-first outreach campaign.")

    lines.append("\n3. RECOMMENDED ANGLE:")
    if cfpb_data.get("complaint_count", 0) > 0:
        lines.append("   - Quality Shield: Focus on customer experience triage to preempt complaints.")
    elif not web_results:
        lines.append("   - Digital Foundation: Build out an automated local lead intake & review capture page.")
    else:
        lines.append("   - Automation & Response: Propose an AI concierge layer to capture off-hours inquiries.")

    lines.append("\n4. CONFIDENCE: Medium (Local rule-based heuristic synthesis)")
    return "\n".join(lines)


def scout_target(name, location=None, cfpb_only=False, web_only=False):
    print(f"\n{'='*55}\n  SWARM INTEL -- {name}\n{'='*55}")

    cfpb_data = {"complaint_count": 0, "complaints": [], "risk_flags": []}
    web_data = {"results": [], "risk_flags": [], "opportunity_flags": []}

    if not web_only:
        print("  [CFPB] ...", end="", flush=True)
        cfpb_data = get_complaint_summary(name)
        print(f" {cfpb_data.get('complaint_count',0)} complaints")

    if not cfpb_only:
        print("  [WEB]  ...", end="", flush=True)
        web_data = get_business_signals(name, location)
        print(f" {web_data.get('result_count',0)} results")

    print("  [SYNTH] ...", end="", flush=True)
    briefing = synthesize(name, cfpb_data, web_data)
    print(" done")

    all_risk = cfpb_data.get("risk_flags",[]) + web_data.get("risk_flags",[])
    all_opp = web_data.get("opportunity_flags",[])
    has_website = any(
        name.lower().replace(" ","") in r.get("url","").lower()
        for r in web_data.get("results",[])
    )
    if not has_website:
        all_opp.append("No confirmed web presence -- high-value outreach target")

    return {
        "name": name, "location": location,
        "scouted_at": datetime.now().isoformat(),
        "cfpb": cfpb_data, "web": web_data,
        "briefing": briefing,
        "risk_flags": all_risk, "opportunity_flags": all_opp,
        "has_website": has_website,
        "risk_score": min(100, len(all_risk) * 20),
        "opportunity_score": min(100, len(all_opp) * 25 + (cfpb_data.get("complaint_count",0)==0)*20)
    }


def main():
    parser = argparse.ArgumentParser(description="VERTICAL AI -- Swarm Intel")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--target")
    g.add_argument("--batch")
    parser.add_argument("--location")
    parser.add_argument("--cfpb-only", action="store_true")
    parser.add_argument("--web-only", action="store_true")
    parser.add_argument("--pipe", action="store_true")
    parser.add_argument("--outreach", action="store_true")
    parser.add_argument("--out")
    args = parser.parse_args()

    if args.target:
        results = [scout_target(args.target, args.location, args.cfpb_only, args.web_only)]
    else:
        with open(args.batch) as f:
            targets = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        results = [scout_target(t, args.location) for t in targets]

    for r in results:
        print(f"\n{'-'*55}\n  BRIEFING: {r['name']}\n{'-'*55}")
        print(r["briefing"])
        print(f"\n  Risk Score:        {r['risk_score']}/100")
        print(f"  Opportunity Score: {r['opportunity_score']}/100")
        print(f"  Has Website:       {r['has_website']}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = args.out or f"swarm_output_{ts}.json"
    with open(out_path, "w") as f:
        json.dump(results if len(results) > 1 else results[0], f, indent=2)
    print(f"\n  Saved: {out_path}")

    if args.pipe:
        conductor = os.path.join(_root, "vertical_ai.py")
        cmd = [sys.executable, conductor, "--scrape", out_path]
        if args.outreach:
            cmd.append("--outreach")
        print(f"\n  Piping to conductor...")
        subprocess.run(cmd)

if __name__ == "__main__":
    main()
