#!/usr/bin/env python3
"""
VERTICAL AI -- Google Business Scout
Plug your existing scraper into scrape_no_website_businesses().
Output feeds swarm_intel or conductor directly.
"""

import sys, os, json, argparse, subprocess
from datetime import datetime

_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_dir)
sys.path.insert(0, _root)


def scrape_no_website_businesses(category, location, min_rating=4.0, max_results=20):
    """
    PLUG YOUR SCRAPER HERE.
    Return list of dicts:
    [{"name":"","category":"","rating":4.8,"review_count":127,
      "phone":"","address":"","has_website":false,"price_tier":"$$","source":"google_business"}]
    """
    raise NotImplementedError("Wire your existing scraper into this function.")


def filter_targets(businesses, min_rating=4.0):
    return [b for b in businesses if not b.get("has_website",True) and b.get("rating",0) >= min_rating]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--min-rating", type=float, default=4.0)
    parser.add_argument("--max-results", type=int, default=20)
    parser.add_argument("--pipe", action="store_true")
    parser.add_argument("--out")
    args = parser.parse_args()

    try:
        raw = scrape_no_website_businesses(args.category, args.location, args.min_rating, args.max_results)
    except NotImplementedError as e:
        print(f"  {e}")
        sys.exit(1)

    filtered = filter_targets(raw, args.min_rating)
    print(f"  {len(raw)} total -> {len(filtered)} qualify")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = args.out or f"google_business_{ts}.json"
    with open(out_path,"w") as f:
        json.dump(filtered, f, indent=2)
    print(f"  Saved: {out_path}")

    if args.pipe:
        swarm = os.path.join(_dir, "swarm_intel.py")
        subprocess.run([sys.executable, swarm, "--batch", out_path])

if __name__ == "__main__":
    main()
