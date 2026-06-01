#!/usr/bin/env python3
"""Generate printable one-page pitch reports from boardroom sessions."""
import json, os, glob
from datetime import datetime

SESSIONS = {
    'RCB_Bank': 'vai_output_vai_42b64cf906b6.json',
    'Chew_Plumbing': 'vai_output_vai_6eacfb40ad0c.json',
    'Countryside_Motors': 'vai_output_vai_7ed97c9a1310.json',
    'Restaurant_General': 'vai_output_vai_d807f2ee7ec9.json',
    'Rural_Revive': 'vai_output_vai_1a3798be282b.json',
}

def format_report(name, data):
    champion = data.get('champion', {})
    boardroom = data.get('boardroom', {})
    synthesis = boardroom.get('synthesis', {})
    outreach = data.get('outreach', {})

    report = f"""
{'='*60}
PITCH REPORT: {name.replace('_',' ').upper()}
Generated: {datetime.now().strftime('%Y-%m-%d')}
{'='*60}

STRATEGY: {champion.get('name','N/A')}
{champion.get('thesis','')}

FIRST ACTION:
{champion.get('first_action','')}

TARGET OUTCOME:
{champion.get('target_outcome','')}

BOARDROOM VERDICT: {synthesis.get('verdict','N/A').upper()}
Risk:        {synthesis.get('primary_risk','')}
Opportunity: {synthesis.get('primary_opportunity','')}

{'='*60}
OUTREACH
{'='*60}
Subject: {outreach.get('subject_line','N/A')}

Hook: {outreach.get('hook','')}

Value: {outreach.get('value_proposition','')}

Pain: {outreach.get('pain_point_addressed','')}

CTA: {outreach.get('call_to_action','')}

EMAIL:
{outreach.get('platform_variants',{}).get('email','')}

OBJECTIONS:
No budget: {outreach.get('objection_handlers',{}).get('no budget','')}

Not interested: {outreach.get('objection_handlers',{}).get('not interested','')}

{'='*60}
"""
    return report

os.makedirs('reports', exist_ok=True)

for name, filename in SESSIONS.items():
    if not os.path.exists(filename):
        print(f"Missing: {filename}")
        continue
    with open(filename) as f:
        data = json.load(f)
    report = format_report(name, data)
    out = f"reports/{name}_pitch.txt"
    with open(out, 'w') as f:
        f.write(report)
    print(f"Saved: {out}")

print("\nAll reports in: reports/")
print("Copy to /storage/emulated/0/GRAB/ to print from any device")
