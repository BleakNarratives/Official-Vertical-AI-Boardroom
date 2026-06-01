#!/usr/bin/env python3
"""Firefly Lite -- free government data, no auth, no blocks"""
import urllib.request, urllib.parse, json, os, csv
from datetime import datetime
from io import StringIO

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; research/1.0)'}

def fetch(url, json_response=True):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode('utf-8', errors='replace')
        if json_response:
            return json.loads(raw), None
        return raw, None
    except Exception as e:
        return None, str(e)

def fetch_bls(series_id):
    """BLS -- employment/wages by industry"""
    url = f"https://api.bls.gov/publicAPI/v1/timeseries/data/{series_id}"
    data, err = fetch(url)
    if err or not data:
        return f"BLS error: {err}"
    try:
        points = data['Results']['series'][0]['data'][:6]
        out = [f"  {p['periodName']} {p['year']}: {p['value']}K employees" for p in points]
        return "BLS Employment (thousands):\n" + "\n".join(out)
    except:
        return "BLS: parse error"

def fetch_fred(series_id, label):
    """FRED -- economic time series"""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    raw, err = fetch(url, json_response=False)
    if err or not raw:
        return f"FRED error: {err}"
    try:
        lines = raw.strip().split('\n')
        recent = lines[-6:]
        out = [f"  {line}" for line in recent]
        return f"FRED {label} (recent):\n" + "\n".join(out)
    except:
        return "FRED: parse error"

def fetch_worldbank(indicator, label):
    """World Bank -- macro indicators"""
    url = f"https://api.worldbank.org/v2/country/US/indicator/{indicator}?format=json&mrv=4"
    data, err = fetch(url)
    if err or not data:
        return f"WorldBank error: {err}"
    try:
        points = data[1][:4]
        out = [f"  {p['date']}: ${p['value']:,.0f}" for p in points if p['value']]
        return f"WorldBank {label}:\n" + "\n".join(out)
    except:
        return "WorldBank: parse error"

def fetch_hn(query):
    """HackerNews -- operator sentiment"""
    url = f"https://hn.algolia.com/api/v1/search?query={urllib.parse.quote(query)}&tags=story&hitsPerPage=6"
    data, err = fetch(url)
    if err or not data:
        return f"HN error: {err}"
    try:
        hits = data.get('hits', [])
        out = [f"  [{h.get('points',0)}pts] {h.get('title','')}" for h in hits]
        return "HackerNews Signal:\n" + "\n".join(out)
    except:
        return "HN: parse error"

# Vertical configs -- BLS series + FRED series + WB indicator
VERTICALS = {
    'restaurant': {
        'bls': 'CEU7072200001',      # food service employment
        'fred': ('MRTSSM722USS', 'Restaurant Sales $M'),
        'wb': ('NY.GDP.MKTP.CD', 'US GDP'),
        'hn_query': 'restaurant small business online ordering margins',
        'manual': """OPERATOR INTEL:
- Toast POS: $110/mo, 0% commission on own orders
- DoorDash/UberEats commission: 15-30% per order
- Avg restaurant net margin: 3-9%
- Online ordering raises avg ticket 20-30%
- Labor = 30-35% of revenue (biggest cost)
- Food cost target: 28-35% of revenue
- Break-even typically 18-24 months"""
    },
    'plumber': {
        'bls': 'CEU2000000001',
        'fred': ('HOUST', 'Housing Starts -- correlates plumbing demand'),
        'wb': ('NY.GDP.MKTP.CD', 'US GDP'),
        'hn_query': 'plumber small business leads pricing',
        'manual': """OPERATOR INTEL:
- Avg service call: $175-450
- Emergency premium: 1.5-2x standard rate
- Lead gen platforms: Angi, Thumbtack, HomeAdvisor 15-25% fees
- License required all 50 states
- Biggest pain: no-shows, price shoppers, slow seasons"""
    },
    'saas': {
        'bls': 'CEU5051000001',
        'fred': ('PCEC96', 'Real Personal Consumption'),
        'wb': ('NY.GDP.MKTP.CD', 'US GDP'),
        'hn_query': 'SaaS churn pricing bootstrapped revenue',
        'manual': """OPERATOR INTEL:
- Avg SaaS churn: 5-7% monthly for SMB
- CAC payback target: under 12 months
- NRR > 100% = growth without new customers
- Pricing anchors: $29/$99/$299 tiers standard
- Free trial converts at 2-5%, freemium at 1-3%"""
    },
    'retail': {
        'bls': 'CEU4200000001',
        'fred': ('RSAFS', 'Retail Sales'),
        'wb': ('NY.GDP.MKTP.CD', 'US GDP'),
        'hn_query': 'retail small business inventory ecommerce margins',
        'manual': """OPERATOR INTEL:
- Avg retail margin: 20-50% gross, 2-6% net
- Shopify + ads CAC eating margins industry-wide
- Inventory carrying cost: 20-30% of value annually
- Returns: 15-40% online vs 8-10% in-store"""
    },
}

def build_vertical_context(vertical, extra_keywords="", deep=False):
    print(f"[Firefly] Scouting: {vertical}...")
    
    config = VERTICALS.get(vertical.lower())
    sections = []

    if config:
        # Manual curated intel always included
        sections.append(config['manual'])

        if deep:
            print(f"  BLS...", end="", flush=True)
            bls = fetch_bls(config['bls'])
            sections.append(bls)
            print(" ok")

            print(f"  FRED...", end="", flush=True)
            fred = fetch_fred(config['fred'][0], config['fred'][1])
            sections.append(fred)
            print(" ok")

            print(f"  WorldBank...", end="", flush=True)
            wb = fetch_worldbank(config['wb'][0], config['wb'][1])
            sections.append(wb)
            print(" ok")

            print(f"  HackerNews...", end="", flush=True)
            hn = fetch_hn(config['hn_query'] + " " + extra_keywords)
            sections.append(hn)
            print(" ok")
    else:
        # Unknown vertical -- HN only
        print(f"  HN fallback...", end="", flush=True)
        hn = fetch_hn(f"{vertical} {extra_keywords} small business problems")
        sections.append(hn)
        print(" ok")

    out_dir = os.path.join(os.path.dirname(__file__), 'verticals')
    os.makedirs(out_dir, exist_ok=True)
    fname = f"{vertical.replace(' ','_').lower()}.txt"
    out_file = os.path.join(out_dir, fname)

    content = f"""DOMAIN CONTEXT -- {vertical.upper()}
Generated: {datetime.now().isoformat()}
Keywords: {extra_keywords}

{"=" * 50}
{chr(10).join(sections)}
"""
    with open(out_file, 'w') as f:
        f.write(content)

    print(f"[Firefly] {len(content)} chars saved to verticals/{fname}")
    return out_file, content

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--vertical', required=True)
    parser.add_argument('--keywords', default="")
    parser.add_argument('--deep', action='store_true', help='Pull live govt data')
    args = parser.parse_args()
    build_vertical_context(args.vertical, args.keywords, args.deep)
