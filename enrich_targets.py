#!/usr/bin/env python3
"""Manual enrichment -- paste real Google data for each target"""
import json, os

targets = [
    {"name": "Impact Bank", "location": "Wellington KS", "category": "bank"},
    {"name": "RCB Bank", "location": "Wellington KS", "category": "bank"},
    {"name": "Fabiola's Mexican Restaurant", "location": "Wellington KS", "category": "restaurant"},
    {"name": "Canelo's Mexican Grill", "location": "Wellington KS", "category": "restaurant"},
    {"name": "Penny's Diner", "location": "Wellington KS", "category": "restaurant"},
    {"name": "Big Cheese Pizza", "location": "Wellington KS", "category": "restaurant"},
    {"name": "Chew Plumbing", "location": "Wellington KS", "category": "plumber"},
    {"name": "Countryside Motors", "location": "Wellington KS", "category": "auto dealer"},
]

print("Google each business and enter real data:\n")
enriched = []
for t in targets:
    print(f"=== {t['name']} ===")
    rating = input("  Google rating (or enter to skip): ").strip()
    reviews = input("  Review count (or enter to skip): ").strip()
    website = input("  Has website? y/n: ").strip()
    t['rating'] = float(rating) if rating else None
    t['reviews'] = int(reviews) if reviews else None
    t['has_website'] = website.lower() == 'y'
    enriched.append(t)
    print()

with open('targets/enriched_wellington.json', 'w') as f:
    json.dump(enriched, f, indent=2)
print("Saved to targets/enriched_wellington.json")
