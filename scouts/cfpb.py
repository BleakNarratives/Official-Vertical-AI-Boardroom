#!/usr/bin/env python3
"""
VERTICAL AI -- CFPB Scout
Live Consumer Financial Protection Bureau data. Real endpoint.
"""

import requests
import json
import sys

CFPB_API = "https://api.consumerfinance.gov/data/complaints/search.json"


def fetch_complaints(company_name: str, limit: int = 5) -> list:
    params = {"search_term": company_name, "size": limit, "sort": "created_date_desc"}
    try:
        resp = requests.get(CFPB_API, params=params, timeout=10)
        resp.raise_for_status()
        hits = resp.json().get("hits",{}).get("hits",[])
        return [{
            "product": h.get("_source",{}).get("product",""),
            "issue": h.get("_source",{}).get("issue",""),
            "state": h.get("_source",{}).get("state",""),
            "date_received": h.get("_source",{}).get("date_received",""),
            "company_response": h.get("_source",{}).get("company_response",""),
            "timely_response": h.get("_source",{}).get("timely",""),
            "narrative": h.get("_source",{}).get("complaint_what_happened","")[:300]
        } for h in hits]
    except Exception as e:
        return [{"error": str(e)}]


def get_complaint_summary(company_name: str) -> dict:
    complaints = fetch_complaints(company_name, 10)
    real = [c for c in complaints if "error" not in c]
    issues = list(set(c.get("issue","") for c in real if c.get("issue")))
    products = list(set(c.get("product","") for c in real if c.get("product")))
    risk_flags = []
    if len(real) >= 5:
        risk_flags.append(f"HIGH volume: {len(real)} recent CFPB complaints")
    if any(p in products for p in ["Mortgage","Debt collection"]):
        risk_flags.append("Regulated product area flagged")
    untimely = [c for c in real if c.get("timely_response") == "No"]
    if untimely:
        risk_flags.append(f"{len(untimely)} untimely responses")
    return {"company": company_name, "complaint_count": len(real), "complaints": real,
            "issues_reported": issues, "products_affected": products, "risk_flags": risk_flags}


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "Wells Fargo"
    print(json.dumps(get_complaint_summary(target), indent=2))
