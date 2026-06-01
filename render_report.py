#!/usr/bin/env python3
"""
render_report.py
Turns any vai_output_*.json into a clean client-ready one-pager.
Usage: python3 render_report.py vai_output_vai_899b9cd46f2d.json
"""
import json
import sys
from pathlib import Path

def render(path: str):
    data = json.loads(Path(path).read_text())
    c = data.get("champion", {})
    ctx = data.get("context", {})
    question = ctx.get("raw", "")[:120]

    print(f"\nSTRATEGIC ANALYSIS REPORT")
    print(f"Session: {data.get('session_id','')}\n")

    if question:
        print(f"INPUT\n{question}\n")

    print(f"STRATEGY\n{c.get('name','')}\n")
    print(f"THESIS\n{c.get('thesis','')}\n")
    print(f"FIRST ACTION\n{c.get('first_action','')}\n")
    print(f"BUILT FROM\n- {c.get('inherited_from_a','')}\n- {c.get('inherited_from_b','')}\n")
    print(f"KEY DIFFERENTIATOR\n{c.get('mutation','')}\n")
    print(f"TARGET OUTCOME\n{c.get('target_outcome','')}\n")

if __name__ == "__main__":
    render(sys.argv[1] if len(sys.argv) > 1 else sorted(Path(".").glob("vai_output_*.json"))[-1])
