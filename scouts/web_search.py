#!/usr/bin/env python3
"""
VERTICAL AI -- Web Search Scout
DuckDuckGo. No API key. Real signals.
"""

import json
import sys
from typing import Optional


def search(query: str, max_results: int = 5) -> list:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            return [{"title": r.get("title",""), "url": r.get("href",""),
                     "snippet": r.get("body",""), "source": "duckduckgo"}
                    for r in ddgs.text(query, max_results=max_results)]
    except ImportError:
        return [{"error": "run: pip install duckduckgo-search --break-system-packages"}]
    except Exception as e:
        return [{"error": str(e)}]


def get_business_signals(business_name: str, location: Optional[str] = None) -> dict:
    queries = [
        f"{business_name} reviews complaints",
        f"{business_name} {location} news" if location else f"{business_name} news",
        f"{business_name} website"
    ]
    all_results = []
    seen = set()
    for q in queries:
        for r in search(q, 3):
            url = r.get("url","")
            if url and url not in seen:
                seen.add(url)
                all_results.append(r)

    risk_flags, opportunity_flags = [], []
    for r in all_results:
        text = (r.get("snippet","") + r.get("title","")).lower()
        if any(w in text for w in ["lawsuit","fraud","scam","complaint","violation","fine"]):
            risk_flags.append(f"Negative: {r.get('title','')[:80]}")
        if any(w in text for w in ["award","best","top rated","expanding","hiring"]):
            opportunity_flags.append(f"Positive: {r.get('title','')[:80]}")

    return {"business": business_name, "location": location, "results": all_results,
            "result_count": len(all_results), "risk_flags": risk_flags, "opportunity_flags": opportunity_flags}


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "Mikes Plumbing Phoenix"
    print(json.dumps(get_business_signals(target), indent=2))
