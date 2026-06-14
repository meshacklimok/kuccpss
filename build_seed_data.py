"""
Helper script to build normalization data for the TVET seed command.
Run once to inspect the data, then use output in seed_tvet.py.
"""
import json, re
from collections import defaultdict

with open('tvet_raw_data.json', encoding='utf-8') as f:
    data = json.load(f)

offerings = data['offerings']

# Normalize programme names to canonical forms
def normalize(name):
    n = name.strip().upper()
    # Remove common noise
    n = re.sub(r'\s+', ' ', n)
    n = n.replace('DIPLOMA IN ', '')
    return n

# Group by normalized name
groups = defaultdict(list)
for o in offerings:
    groups[normalize(o['programme'])].append(o['programme'])

# Show groups with >1 variant
variants = {k: sorted(set(v)) for k, v in groups.items() if len(set(v)) > 1}
print(f"Groups with variants: {len(variants)}")
for k, v in sorted(variants.items())[:30]:
    print(f"  {k}: {v}")

# Unique institutions sorted
insts = sorted(set(o['institution'] for o in offerings))
print(f"\nUnique institutions: {len(insts)}")
