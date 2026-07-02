#!/usr/bin/env python3
"""
Extract KUCCPS Degree Programme Cut Offs PDF → CSV for CourseOffering import.

Install dependency:  pip install pdfplumber
Usage:               python scripts/extract_degree_cutoffs.py <path/to/cutoffs.pdf> <output.csv>

Output CSV columns (matches CourseOfferingResource):
    course_name, course_type, institution, cutoff_2024, cutoff_2023, cutoff_2022, cutoff_2021
"""

import sys
import csv
import pdfplumber


YEARS = ['2021', '2022', '2023', '2024']   # 4 years to keep


def clean_text(val):
    if not val:
        return ''
    return ' '.join(str(val).split())   # collapse whitespace / newlines


def clean_num(val):
    if not val:
        return ''
    v = str(val).strip().replace(',', '.')
    try:
        return str(round(float(v), 3))
    except ValueError:
        return ''


def find_header_row(table):
    """Return index of the row that contains 'INSTITUTION' and 'PROGRAMME', or -1."""
    for i, row in enumerate(table):
        texts = [str(c).upper() if c else '' for c in row]
        if any('INSTITUTION' in t for t in texts) and any('PROGRAMME' in t for t in texts):
            return i
    return -1


def extract_column_indices(header_row):
    """
    Given the header row cells, return a dict:
        { 'institution': idx, 'programme': idx, '2021': idx, '2022': idx, '2023': idx, '2024': idx }
    Returns None if required columns are missing.
    """
    idx = {}
    for i, cell in enumerate(header_row):
        t = str(cell).upper().strip() if cell else ''
        if 'INSTITUTION' in t:
            idx['institution'] = i
        elif 'PROGRAMME' in t:
            idx['programme'] = i
        else:
            for year in YEARS:
                if year in t:
                    idx[year] = i
    if 'institution' not in idx or 'programme' not in idx:
        return None
    return idx


def extract_rows(pdf_path):
    all_data = []
    col_idx = None

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            table = page.extract_table()
            if not table:
                continue

            # Find/re-find header on each page (repeated headers)
            header_row_idx = find_header_row(table)
            if header_row_idx >= 0:
                detected = extract_column_indices(table[header_row_idx])
                if detected:
                    col_idx = detected
                start = header_row_idx + 1
            else:
                start = 0

            if col_idx is None:
                print(f"  [page {page_num}] skipped — header not found yet")
                continue

            for row in table[start:]:
                if not row:
                    continue
                cells = [clean_text(c) for c in row]

                institution = cells[col_idx['institution']] if col_idx['institution'] < len(cells) else ''
                programme   = cells[col_idx['programme']]   if col_idx['programme']   < len(cells) else ''

                if not institution or not programme:
                    continue

                # Skip obvious section-header rows (no numeric data at all)
                year_vals = {}
                for year in YEARS:
                    if year in col_idx and col_idx[year] < len(cells):
                        year_vals[year] = clean_num(cells[col_idx[year]])
                    else:
                        year_vals[year] = ''

                if not any(year_vals.values()):
                    continue

                all_data.append({
                    'course_name': programme,
                    'institution': institution,
                    **{f'cutoff_{y}': year_vals[y] for y in YEARS},
                })

    return all_data


def write_csv(rows, output_path):
    fieldnames = ['course_name', 'course_type', 'institution',
                  'cutoff_2024', 'cutoff_2023', 'cutoff_2022', 'cutoff_2021']
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                'course_name':  row['course_name'],
                'course_type':  'Degree',
                'institution':  row['institution'],
                'cutoff_2024':  row.get('cutoff_2024', ''),
                'cutoff_2023':  row.get('cutoff_2023', ''),
                'cutoff_2022':  row.get('cutoff_2022', ''),
                'cutoff_2021':  row.get('cutoff_2021', ''),
            })


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    pdf_path    = sys.argv[1]
    output_path = sys.argv[2]

    print(f"Reading: {pdf_path}")
    rows = extract_rows(pdf_path)
    print(f"Extracted {len(rows)} data rows")

    write_csv(rows, output_path)
    print(f"Saved -> {output_path}")
    print()
    print("Next steps:")
    print("  1. Open the CSV and verify a few rows look correct")
    print("  2. Go to /admin/courses/courseoffering/import/")
    print("  3. Upload the CSV — it will create courses and match institutions by name")
