#!/usr/bin/env python3
"""
VERTICAL AI -- Fractal Simulator
Action -> market response chains. Real reasoning only.
"""

import json
from router import call_model, ModelTier


def simulate_track(track: dict, iterations: int = 4) -> list:
    chain = []
    current_action = track["action"]
    context_summary = json.dumps(track.get("context", {}))

    for i in range(1, iterations + 1):
        market_prompt = f"""
CONTEXT: {context_summary}
ITERATION {i} ACTION: {current_action}

How does the market actually respond? Consider competitors, customers, regulators, press, investors.
Be specific. No vague generalities.

JSON only:
{{"market_response": "what the market does", "sentiment": "positive|negative|neutral|mixed", "key_players_affected": ["who reacts and how"], "opportunity_window": "time before market adjusts"}}
"""
        try:
            raw, provider = call_model(market_prompt, tier=ModelTier.FAST)
            market_data = json.loads(raw.strip().replace("```json","").replace("```","").strip())
        except Exception as e:
            market_data = {"market_response": f"ERROR: {e}", "sentiment": "unknown"}

        counter_prompt = f"""
CONTEXT: {context_summary}
ACTION: {current_action}
MARKET RESPONDED: {json.dumps(market_data)}

Smartest business counter-move given this response?

JSON only:
{{"counter_action": "what business does next", "rationale": "why", "resource_required": "cost in time/money/people", "risk": "what could go wrong"}}
"""
        try:
            raw2, provider2 = call_model(counter_prompt, tier=ModelTier.FAST)
            counter_data = json.loads(raw2.strip().replace("```json","").replace("```","").strip())
        except Exception as e:
            counter_data = {"counter_action": f"ERROR: {e}"}

        chain.append({
            "iteration": i,
            "action": current_action,
            "market_response": market_data,
            "business_counter": counter_data
        })
        current_action = counter_data.get("counter_action", current_action)

    return chain


def run_fractal_simulation(synthesis: dict, input_context: dict, tracks: int = 3, iterations: int = 4) -> list:
    print(f"\n{'='*60}")
    print(f"  VERTICAL AI -- FRACTAL SIMULATION")
    print(f"  {tracks} tracks x {iterations} iterations")
    print(f"{'='*60}\n")

    track_prompt = f"""
BOARDROOM SYNTHESIS: {json.dumps(synthesis, indent=2)}
CONTEXT: {json.dumps(input_context, indent=2)}

Generate exactly {tracks} distinct strategic tracks. Meaningfully different approaches.

JSON only:
{{"tracks": [{{"name": "track name", "thesis": "one sentence", "first_action": "specific first move", "target_outcome": "success in 90 days"}}]}}
Exactly {tracks} tracks. Return ONLY JSON.
"""
    print("  Generating tracks...", end="", flush=True)
    try:
        raw, provider = call_model(track_prompt, tier=ModelTier.BOARDROOM)
        print(f" ({provider})")
        tracks_data = json.loads(raw.strip().replace("```json","").replace("```","").strip())["tracks"]
    except Exception as e:
        print(f"\n  Track generation failed: {e}")
        return []

    simulated = []
    for i, track in enumerate(tracks_data):
        print(f"\n  -- TRACK {i+1}: {track['name']} --")
        print(f"  Thesis: {track['thesis']}")
        chain = simulate_track({"name": track["name"], "action": track["first_action"], "context": input_context}, iterations)
        for step in chain:
            mr = step['market_response']
            bc = step['business_counter']
            print(f"  [{step['iteration']}] {step['action'][:70]}...")
            if isinstance(mr, dict):
                print(f"       Market: {mr.get('market_response','')[:70]}... [{mr.get('sentiment','')}]")
            if isinstance(bc, dict):
                print(f"       Counter: {bc.get('counter_action','')[:70]}...")
        simulated.append({"track_meta": track, "chain": chain, "chain_length": len(chain)})

    return simulated
