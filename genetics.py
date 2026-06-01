#!/usr/bin/env python3
"""
VERTICAL AI -- Genetic Arena
Score. Eliminate. Breed. Champion.
"""

import json
from router import call_model, ModelTier


def score_chain(chain: list, context: dict) -> dict:
    prompt = f"""
CONTEXT: {json.dumps(context)}
CHAIN: {json.dumps(chain, indent=2)[:3000]}

Score this strategy. Be harsh. Most strategies are mediocre.

JSON only:
{{"market_adaptability": 0-100, "resource_efficiency": 0-100, "competitive_defensibility": 0-100, "execution_realism": 0-100, "upside_potential": 0-100, "overall_fitness": 0-100, "fatal_flaw": "what kills this or null", "strongest_gene": "best element worth preserving"}}
"""
    try:
        raw, provider = call_model(prompt, tier=ModelTier.FAST)
        scores = json.loads(raw.strip().replace("```json","").replace("```","").strip())
        scores["provider"] = provider
        return scores
    except Exception as e:
        return {"overall_fitness": 0, "error": str(e)}


def breed(parent_a: dict, parent_b: dict, context: dict) -> dict:
    a = parent_a.get("scores", {})
    b = parent_b.get("scores", {})
    prompt = f"""
CONTEXT: {json.dumps(context)}

PARENT A: {parent_a.get('track_meta',{}).get('thesis','')}
Strongest gene: {a.get('strongest_gene','')}
Fatal flaw: {a.get('fatal_flaw','')}

PARENT B: {parent_b.get('track_meta',{}).get('thesis','')}
Strongest gene: {b.get('strongest_gene','')}
Fatal flaw: {b.get('fatal_flaw','')}

Breed these. Preserve strongest genes. Eliminate fatal flaws.
Introduce ONE mutation neither parent considered.

JSON only:
{{"name": "offspring name", "thesis": "one sentence", "first_action": "specific first move", "inherited_from_a": "what came from A", "inherited_from_b": "what came from B", "mutation": "new element neither parent had", "target_outcome": "success in 90 days"}}
"""
    try:
        raw, provider = call_model(prompt, tier=ModelTier.BOARDROOM)
        result = json.loads(raw.strip().replace("```json","").replace("```","").strip())
        result["provider"] = provider
        return result
    except Exception as e:
        return {"name": "BREED_FAILED", "error": str(e)}


def run_arena(simulated_tracks: list, context: dict, generations: int = 2) -> dict:
    print(f"\n{'='*60}")
    print(f"  VERTICAL AI -- GENETIC ARENA")
    print(f"  {len(simulated_tracks)} contestants")
    print(f"{'='*60}\n")

    population = simulated_tracks

    for gen in range(1, generations + 1):
        print(f"-- GENERATION {gen} -- population: {len(population)}")

        for ind in population:
            if not ind.get("scores"):
                name = ind.get("track_meta",{}).get("name","unknown")
                print(f"  Scoring: {name}...", end="", flush=True)
                ind["scores"] = score_chain(ind.get("chain",[]), context)
                print(f" fitness={ind['scores'].get('overall_fitness',0)}")

        population.sort(key=lambda x: x.get("scores",{}).get("overall_fitness",0), reverse=True)

        print("\n  ARENA:")
        cutoff = max(2, len(population)//2 + len(population)%2)
        for i, ind in enumerate(population):
            name = ind.get("track_meta",{}).get("name", f"Strategy {i+1}")
            fitness = ind.get("scores",{}).get("overall_fitness",0)
            status = "SURVIVES" if i < cutoff else "ELIMINATED"
            print(f"  [{fitness:3.0f}] {name} -- {status}")

        survivors = population[:cutoff]
        if len(survivors) <= 2:
            population = survivors
            break

        offspring = list(survivors)
        pairs = list(zip(survivors[::2], survivors[1::2]))
        print(f"\n  Breeding {len(pairs)} pairs...")
        for pa, pb in pairs:
            child = breed(pa, pb, context)
            print(f"  -> {child.get('name','offspring')}")
            offspring.append({"track_meta": child, "chain": [], "scores": {}})

        population = offspring

    print("\n-- FINAL BREED -- CHAMPION EXTRACTION --")
    if len(population) >= 2:
        champion = breed(population[0], population[1], context)
        print(f"  CHAMPION: {champion.get('name','')}")
    else:
        champion = population[0].get("track_meta",{})

    return {
        "champion": champion,
        "finalists": [p.get("track_meta") for p in population[:2]],
        "generations_run": gen
    }
