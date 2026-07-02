#!/usr/bin/env python3
"""
Extract KUCCPS Degree Programmes Clusters PDF -> CSV for cluster seeding.

Usage:
    python scripts/extract_cluster_programmes.py <path/to/clusters.pdf> data/clusters_map.csv

Output CSV columns:
    cluster_code, programme_name, requirements
    e.g.: 1A, Bachelor of Laws (LL.B.), ENG/KIS >= B (PLAIN)
          5A, Bachelor of Engineering (Chemical and Process Engineering), MAT ALTERNATIVE A - C+  PHY - C+  CHE - C+  ENG/KIS - C+
"""

import sys
import re
import csv
import pdfplumber

# Sub-cluster codes: 1-20 followed by A-K, at the start of a line
# Handles: "1A Bachelor of Laws", "2A MAT ALTERNATIVE A/B", "3D" (alone), "3B ENG C+"
SUBCLUSTER_RE = re.compile(r'^(\d{1,2}[A-K])\b\s*(.*)', re.DOTALL)

def looks_like_programme(text):
    return bool(re.match(r'^Bachelor\b', text.strip(), re.IGNORECASE))

def clean(s):
    return ' '.join((s or '').split())

# Split a line at any "Bachelor" that is preceded by non-whitespace — handles
# single-space two-column PDF layout where pdfplumber doesn't preserve wide gaps.
SPLIT_RE = re.compile(r'(?<=\S)\s+(?=Bachelor\b)', re.IGNORECASE)

def split_programmes(text):
    parts = SPLIT_RE.split(text)
    return [clean(p) for p in parts if looks_like_programme(clean(p))]

def extract(pdf_path):
    current_cluster = None
    requirements_map = {}  # code -> requirements text
    rows = []  # (cluster_code, programme_name, requirements)

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for raw_line in text.split('\n'):
                line = raw_line.strip()
                if not line:
                    continue

                # Check if line starts with a sub-cluster code
                m = SUBCLUSTER_RE.match(line)
                if m:
                    current_cluster = m.group(1)
                    rest = m.group(2).strip()
                    if rest:
                        # Find where the first Bachelor programme starts (if any)
                        bachelor_match = re.search(r'\bBachelor\b', rest, re.IGNORECASE)
                        if bachelor_match and bachelor_match.start() == 0:
                            # Entire rest is programme(s), no requirements on this line
                            for prog in split_programmes(rest):
                                rows.append((current_cluster, prog, requirements_map.get(current_cluster, '')))
                        elif bachelor_match:
                            # Part before first Bachelor is requirements
                            req_text = clean(rest[:bachelor_match.start()])
                            prog_text = rest[bachelor_match.start():]
                            requirements_map[current_cluster] = req_text
                            for prog in split_programmes(prog_text):
                                rows.append((current_cluster, prog, req_text))
                        else:
                            # Pure requirements text (no Bachelor on this line)
                            requirements_map[current_cluster] = clean(rest)
                    continue

                if not current_cluster:
                    continue

                for prog in split_programmes(line):
                    rows.append((current_cluster, prog, requirements_map.get(current_cluster, '')))

    return rows

def write_csv(rows, path):
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['cluster_code', 'programme_name', 'requirements'])
        for cluster, prog, req in rows:
            w.writerow([cluster, prog, req])

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    rows = extract(sys.argv[1])
    write_csv(rows, sys.argv[2])
    print(f"Extracted {len(rows)} programme-cluster pairs -> {sys.argv[2]}")
    codes = sorted({r[0] for r in rows})
    print(f"Cluster codes found ({len(codes)}): {', '.join(codes)}")
    # Show requirements sample
    seen = {}
    for code, prog, req in rows:
        if code not in seen and req:
            seen[code] = req
    print(f"\nSample requirements ({len(seen)} clusters have requirements):")
    for code, req in sorted(seen.items())[:10]:
        print(f"  {code}: {req}")
