#!/usr/bin/env python3
"""
Firefly Target Scout -- autonomous local business discovery
Finds viable targets, scores them, preps vertical context
Usage: python3 scout_targets.py --location "Wellington KS" --radius 20
"""
import urllib.request, urllib.parse, json, os, time
from datetime import datetime

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; research/1.0)'}

def fetch(url, json_resp=True):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode('utf-8', errors='replace')
        return (json.loads(raw) if json_resp else raw), None
    except Exception as e:
        return None, str(e)

def score_viability(business):
    """
    Score a business 0-100 for pitch viability.
    Sweet spot: established enough to pay, small enough to decide fast.
    """
    score = 0
    reasons = []
    flags = []

    rating = business.get('rating', 0)
    review_count = business.get('review_count', 0)
    has_website = business.get('has_website', False)
    category = business.get('category', '').lower()

    # Rating sweet spot: 3.5-4.6
    # Too low = they know they have problems but won't pay
    # Too high = they think they don't need help
    if 3.5 <= rating <= 4.3:
        score += 30
        reasons.append(f"Rating {rating} -- motivated to improve")
    elif 4.3 < rating <= 4.7:
        score += 20
        reasons.append(f"Rating {rating} -- successful, pitch growth not repair")
    elif rating < 3.5:
        score += 10
        flags.append(f"Rating {rating} -- may be resistant or in denial")
    elif rating > 4.7:
        score += 10
        flags.append(f"Rating {rating} -- may think they don't need help")

    # Review count sweet spot: 50-400
    if 50 <= review_count <= 400:
        score += 25
        reasons.append(f"{review_count} reviews -- established but not corporate")
    elif review_count < 50:
        score += 10
        flags.append(f"Only {review_count} reviews -- may be too new or too small")
    elif review_count > 400:
        score += 15
        flags.append(f"{review_count} reviews -- may already have marketing team")

    # No website or bad website = opportunity
    if not has_website:
        score += 25
        reasons.append("No website -- immediate digital opportunity")
    else:
        score += 10
        reasons.append("Has website -- pitch AI layer on top")

    # High value verticals
    high_value = ['plumb', 'hvac', 'heat', 'cool', 'electric', 'auto', 'dealer',
                  'mechanic', 'restaurant', 'dental', 'legal', 'accountant', 'roof']
    for v in high_value:
        if v in category:
            score += 20
            reasons.append(f"High-value vertical: {category}")
            break

    return min(score, 100), reasons, flags

def map_to_vertical(category):
    """Map business category to our vertical context files."""
    category = category.lower()
    mapping = {
        'plumb': 'plumber',
        'hvac': 'hvac',
        'heat': 'hvac',
        'cool': 'hvac',
        'restaurant': 'restaurant',
        'food': 'restaurant',
        'pizza': 'restaurant',
        'diner': 'restaurant',
        'auto': 'auto dealer',
        'dealer': 'auto dealer',
        'mechanic': 'auto dealer',
        'car': 'auto dealer',
        'dental': 'dental',
        'legal': 'legal',
        'lawyer': 'legal',
        'attorney': 'legal',
        'roof': 'contractor',
        'electric': 'contractor',
        'construct': 'contractor',
    }
    for key, vertical in mapping.items():
        if key in category:
            return vertical
    return 'small business'

def search_yelp_fusion(location, category, limit=10):
    """
    Yelp Fusion API -- requires free API key
    Get one at: https://www.yelp.com/developers
    """
    api_key = os.getenv('YELP_API_KEY', '')
    if not api_key:
        return None, "No YELP_API_KEY -- get free key at yelp.com/developers"

    url = f"https://api.yelp.com/v3/businesses/search?location={urllib.parse.quote(location)}&categories={urllib.parse.quote(category)}&limit={limit}&sort_by=rating"
    try:
        req = urllib.request.Request(url, headers={
            **HEADERS,
            'Authorization': f'Bearer {api_key}'
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        return data.get('businesses', []), None
    except Exception as e:
        return None, str(e)

def search_overpass(location, amenity, radius_km=20):
    """
    OpenStreetMap Overpass API -- completely free, no key
    Finds businesses by type within radius
    """
    # Geocode location first
    geo_url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(location)}&format=json&limit=1"
    geo_data, err = fetch(geo_url)
    if err or not geo_data:
        return None, f"Geocode failed: {err}"

    lat = float(geo_data[0]['lat'])
    lon = float(geo_data[0]['lon'])
    radius_m = radius_km * 1000

    # Overpass query
    query = f"""
[out:json][timeout:25];
(
  node["amenity"="{amenity}"](around:{radius_m},{lat},{lon});
  way["amenity"="{amenity}"](around:{radius_m},{lat},{lon});
);
out body;
"""
    url = "https://overpass-api.de/api/interpreter"
    try:
        data = urllib.parse.urlencode({'data': query}).encode()
        req = urllib.request.Request(url, data=data, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read())
        return result.get('elements', []), None
    except Exception as e:
        return None, str(e)

def search_nominatim(location, business_type, radius_km=20):
    """Search for businesses using Nominatim -- free, no key"""
    geo_url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(business_type + ' near ' + location)}&format=json&limit=15&addressdetails=1"
    time.sleep(1)  # Nominatim rate limit
    data, err = fetch(geo_url)
    if err or not data:
        return [], f"Search failed: {err}"
    return data, None

def fetch_google_places(location, business_type, api_key):
    """Google Places -- needs API key but most accurate"""
    url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={urllib.parse.quote(business_type + ' in ' + location)}&key={api_key}"
    data, err = fetch(url)
    if err:
        return None, err
    return data.get('results', []), None

def build_target_report(business, score, reasons, flags, vertical):
    """Build a pitch-ready one-pager for a target business."""
    name = business.get('name', 'Unknown')
    rating = business.get('rating', 'N/A')
    reviews = business.get('review_count', 'N/A')
    address = business.get('address', 'N/A')
    phone = business.get('phone', 'N/A')
    website = business.get('website', 'None found')
    category = business.get('category', vertical)

    report = f"""
{'='*60}
TARGET: {name}
VIABILITY SCORE: {score}/100
{'='*60}
Location:  {address}
Phone:     {phone}
Website:   {website}
Category:  {category}
Rating:    {rating} stars ({reviews} reviews)

WHY THEY'RE A TARGET:
{chr(10).join('  + ' + r for r in reasons)}

WATCH OUTS:
{chr(10).join('  ! ' + f for f in flags) if flags else '  None identified'}

RECOMMENDED PRODUCT: {vertical.title()} AI Assistant
SUGGESTED PRICE POINT: $149-299/month
PITCH ANGLE: {"Growth tool for a winning operation" if score > 70 else "Fix the gap between quality and reputation"}

OPENING LINE:
"I noticed {name} has {rating} stars and {reviews} reviews --
you're clearly doing something right. I built a system that
helps businesses like yours stop losing time to tire kickers
and unqualified leads. Takes 10 minutes to show you."

BOARDROOM SESSION: Run with --vertical {vertical.replace(' ','_')}
{'='*60}
"""
    return report

def scout_location(location, radius_km=20, min_score=40):
    """Main scout function -- find and score all targets in area."""
    print(f"\n[Firefly] Scouting: {location} (radius: {radius_km}km)")
    print(f"[Firefly] Minimum viability score: {min_score}/100\n")

    targets = []
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')

    # Target categories to scout
    HUNT_LIST = [
        ('plumber', 'plumber'),
        ('hvac', 'hvac'),
        ('restaurant', 'restaurant'),
        ('auto_repair', 'auto dealer'),
        ('car_dealer', 'auto dealer'),
        ('dentist', 'dental'),
        ('electrician', 'contractor'),
        ('bank', 'banking'),
        ('credit_union', 'banking'),
        ('financial', 'banking'),
    ]

    for osm_type, vertical in HUNT_LIST:
        print(f"  Scanning: {osm_type}...", end="", flush=True)

        # Try Overpass first
        results, err = search_overpass(location, osm_type, radius_km)

        if err or not results:
            # Fall back to Nominatim
            results, err = search_nominatim(location, osm_type, radius_km)
            if err or not results:
                print(f" no results")
                continue

        print(f" {len(results)} found")

        for r in results[:8]:  # Cap per category
            # Extract business info from OSM data
            tags = r.get('tags', {}) if 'tags' in r else {}
            name = tags.get('name') or r.get('display_name', '').split(',')[0]
            if not name or len(name) < 3:
                continue

            business = {
                'name': name,
                'category': osm_type.replace('_', ' '),
                'rating': tags.get('rating', 4.0),  # OSM rarely has ratings
                'review_count': 100,  # Default -- enrich with Yelp if available
                'has_website': bool(tags.get('website') or tags.get('url')),
                'website': tags.get('website', tags.get('url', 'None found')),
                'phone': tags.get('phone', tags.get('contact:phone', 'N/A')),
                'address': f"{tags.get('addr:housenumber','')} {tags.get('addr:street','')} {tags.get('addr:city','')}".strip() or r.get('display_name','N/A')[:60],
            }

            score, reasons, flags = score_viability(business)

            if score >= min_score:
                targets.append({
                    'business': business,
                    'score': score,
                    'reasons': reasons,
                    'flags': flags,
                    'vertical': vertical
                })

        time.sleep(1)  # Rate limit OSM

    # Sort by viability score
    targets.sort(key=lambda x: x['score'], reverse=True)

    # Generate reports
    out_dir = os.path.join(os.path.dirname(__file__), 'targets')
    os.makedirs(out_dir, exist_ok=True)
    report_file = os.path.join(out_dir, f"targets_{timestamp}.txt")

    print(f"\n[Firefly] Found {len(targets)} viable targets\n")

    all_reports = f"FIREFLY TARGET REPORT -- {location}\nGenerated: {datetime.now().isoformat()}\n"
    all_reports += f"Targets found: {len(targets)}\n\n"

    for t in targets[:10]:  # Top 10
        report = build_target_report(
            t['business'], t['score'],
            t['reasons'], t['flags'], t['vertical']
        )
        all_reports += report
        print(report)

        # Auto-prep vertical context
        vertical_file = os.path.join(
            os.path.dirname(__file__),
            'verticals',
            f"{t['vertical'].replace(' ','_').lower()}.txt"
        )
        if not os.path.exists(vertical_file):
            print(f"  [Firefly] Prepping vertical: {t['vertical']}...")
            try:
                from firefly_lite import build_vertical_context
                build_vertical_context(t['vertical'])
            except Exception as e:
                print(f"  [Firefly] Vertical prep failed: {e}")

    with open(report_file, 'w') as f:
        f.write(all_reports)

    print(f"\n[Firefly] Report saved: targets/{os.path.basename(report_file)}")
    print(f"[Firefly] Next: python vertical_ai.py --file targets/{os.path.basename(report_file)} --rounds 1 --tracks 1 --iterations 1 --no-neo4j --outreach")

    return targets, report_file

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Firefly Target Scout')
    parser.add_argument('--location', default='Wellington KS', help='City and state to scout')
    parser.add_argument('--radius', type=int, default=20, help='Radius in km')
    parser.add_argument('--min-score', type=int, default=40, help='Minimum viability score 0-100')
    parser.add_argument('--expand', action='store_true', help='Also scout nearby towns')
    args = parser.parse_args()

    locations = [args.location]
    if args.expand:
        # Expand to nearby towns
        locations += [
            'Winfield KS',
            'Arkansas City KS',
            'Caldwell KS',
            'Harper KS'
        ]

    all_targets = []
    for loc in locations:
        targets, report = scout_location(loc, args.radius, args.min_score)
        all_targets.extend(targets)
        if len(locations) > 1:
            time.sleep(2)

    print(f"\n[Firefly] Total viable targets across all locations: {len(all_targets)}")
