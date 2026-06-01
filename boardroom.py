#!/usr/bin/env python3
"""
VERTICAL AI -- Boardroom Engine
Five agents argue. Chairman synthesizes via Gemini.
No simulated output. No placeholders.
"""

import json
from router import call_model, ModelTier

# Vertical AI Boardroom v1.2 -- distinct voices, real friction
AGENTS = {
    "CFO": {
        "persona": """You are the CFO and you are tired of everyone's optimism.
You have been burned before by ideas that looked good on paper.
You speak in numbers only. If someone makes a claim without data you call it out by name.
You are not mean but you are blunt and you do not soften bad news.
You disagree with the CMO almost reflexively -- they spend, you conserve.
You respect the CRO but think they miss revenue opportunities by being too cautious.
Never start your response with 'I agree'. Find the number that breaks the argument.""",
        "focus": "unit economics, burn rate, CAC, LTV, margins, cash position, ROI timeline"
    },
    "CMO": {
        "persona": """You are the CMO and you believe in the customer above all else.
You think the CFO lives in a spreadsheet and has never talked to an actual human being.
You are optimistic but not naive -- you demand evidence for assumptions about customers.
You get genuinely annoyed when people reduce marketing to a cost line.
You think the CRO kills more good ideas than bad ones.
You speak in customer language: pain points, stories, moments of decision.
Push back hard when someone assumes they know who the customer is without asking.""",
        "focus": "customer psychology, market positioning, acquisition, brand, go-to-market"
    },
    "CRO": {
        "persona": """You are the Chief Risk Officer and your job is to find the thing that kills this.
You are not a pessimist. You are the person who finds the landmine before everyone steps on it.
You have seen companies fail from the exact same pattern being described right now.
You are specific about risk -- not 'this could fail' but 'this will fail because X when Y happens'.
You think the CMO is allergic to bad news and the CFO misses operational fragility for financial metrics.
You do not celebrate when you find a fatal flaw. You just name it clearly and move on.""",
        "focus": "failure modes, legal exposure, operational fragility, competitive threats, reputational risk"
    },
    "MARKET_ANALYST": {
        "persona": """You are the Market Analyst and you only trust data you can cite.
You find it physically painful when people make up market size numbers.
You will correct wrong statistics even if it derails the conversation.
You are the quietest person in the room until someone says something empirically wrong.
Then you are the loudest.
You think the Devil plays games and the CFO cherry-picks numbers.
You bring context nobody else has: comparable exits, timing signals, macro headwinds.""",
        "focus": "market size, competitive landscape, timing, macro trends, comparable exits, real data"
    },
    "DEVIL": {
        "persona": """You are the Devil's Advocate and you are not playing a role -- you actually believe the opposite.
You find the strongest thing someone said and you dismantle it.
Not because you enjoy it but because untested assumptions are how companies die.
You are not contrarian for sport. You are the pressure test.
You will sometimes agree with the room if they are right. But they are rarely all right.
You find consensus suspicious. When everyone agrees something is good, you ask what they are missing.
You are the most interesting person in the room and you know it.""",
        "focus": "challenging consensus, exposing assumptions, inverting the strongest argument, stress testing"
    }
}


def compress_input(context, max_chars=1200):
    """Trim context to fit provider limits."""
    raw = context.get('raw') or context.get('data',{}).get('content','')
    if len(raw) > max_chars:
        half = max_chars // 2
        raw = raw[:half] + "\n...[condensed]...\n" + raw[-half:]
    return {
        'label': context.get('label',''),
        'type': context.get('type',''),
        'session_id': context.get('session_id',''),
        'content': raw
    }


def run_boardroom(context: dict, rounds: int = 2) -> dict:
    compressed = compress_input(context)
    input_summary = json.dumps(compressed, indent=2)
    debate_log = []

    print(f"\n{'='*60}")
    print("  VERTICAL AI -- BOARDROOM IN SESSION")
    print(f"{'='*60}")
    print(f"  Target: {context.get('label', 'Unknown')}")
    print(f"  Type:   {context.get('type', 'Unknown')}")
    print(f"{'='*60}\n")

    for round_num in range(1, rounds + 1):
        print(f"-- ROUND {round_num} --")

        for agent_name, agent in AGENTS.items():
            prior_args = "\n\n".join([
                f"[{e['agent']}]: {e['argument'][:250]}"
                for e in debate_log[-2:]
            ]) if debate_log else "You are the first to speak."

            prompt = f"""BOARDROOM INPUT:
{input_summary}

PRIOR ARGUMENTS:
{prior_args}

YOUR TURN. Be specific. Reference actual input data.
Do not summarize others — respond to them or build on them.
Max 150 words. No hedging. No filler."""

            print(f"  [{agent_name}] ...", end="", flush=True)
            try:
                response, provider = call_model(
                    prompt,
                    system=f"{agent['persona']}\nFocus: {agent['focus']}",
                    tier=ModelTier.BOARDROOM
                )
                print()
                print(f"  {response.strip()}\n")
                debate_log.append({
                    "round": round_num,
                    "agent": agent_name,
                    "argument": response.strip(),
                    "provider": provider
                })
            except RuntimeError as e:
                print(f"\n  FAILED: {e}")
                debate_log.append({
                    "round": round_num,
                    "agent": agent_name,
                    "argument": f"FAILED: {e}",
                    "provider": "none"
                })

    print("\n-- CHAIRMAN SYNTHESIS (Gemini) --")
    print("  Chairman deliberating...", end="", flush=True)

    full_debate = "\n\n".join([
        f"[{e['agent']} R{e['round']}]: {e['argument'][:300]}"
        for e in debate_log
        if not e['argument'].startswith("FAILED")
    ])

    chairman_prompt = f"""You have just chaired a boardroom debate about the following:

{input_summary}

Here is what your board said:

{full_debate}

Now deliver your verdict as Chairman. You are not a committee.
You have heard the arguments. You have made a decision.

Speak plainly. No corporate language. No bullet points.
Write three short paragraphs:
1. What the room agreed on and what remained contested
2. The single biggest risk and the single biggest opportunity
3. Your verdict -- go, no-go, or conditional -- and exactly what condition must be met first

Then on a new line write only: VERDICT: go OR VERDICT: no-go OR VERDICT: conditional

Be direct. Be human. Sound like someone who has made hard calls before."""

    try:
        raw, provider = call_model(chairman_prompt, tier=ModelTier.FAST, chairman=True)
        print(f" ({provider})")
        clean = raw.strip()
        # Extract verdict line
        verdict = "unknown"
        for line in clean.split("\n"):
            if line.strip().startswith("VERDICT:"):
                verdict = line.replace("VERDICT:","").strip().lower()
                break
        synthesis = {
            "verdict": verdict,
            "chairman_statement": clean,
            "primary_risk": "",
            "primary_opportunity": "",
            "consensus": "",
            "contested": ""
        }
    except Exception as e:
        print(f"\n  Chairman failed: {e}")
        synthesis = {"error": str(e)}

    print(f"\n{synthesis.get('chairman_statement','No statement')}")
    print(f"\n  VERDICT: {synthesis.get('verdict','unknown').upper()}")
    return {"debate": debate_log, "synthesis": synthesis}
