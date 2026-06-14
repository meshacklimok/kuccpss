"""
build_tveta_csv.py
==================
Scrapes tveta.go.ke and produces two CSV files:

  tveta_courses.csv        — all courses with IDs and levels
  tveta_offerings.csv      — course → institution mappings (active only)

Usage:
    python build_tveta_csv.py                  # all levels
    python build_tveta_csv.py --levels artisan craft   # specific levels

Requirements: only Python standard library (urllib, html.parser, csv, time)

Output columns — tveta_offerings.csv:
    tveta_course_id, tveta_course_name, tveta_level,
    institution_name, county, status
"""

import csv
import html
import os
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser

# ─── Configuration ───────────────────────────────────────────────────────────

BASE_URL       = "https://www.tveta.go.ke"
COURSES_URL    = f"{BASE_URL}/tvet-courses/"
COURSE_URL     = f"{BASE_URL}/course/?course_id="

OUTPUT_COURSES  = "tveta_courses.csv"
OUTPUT_OFFERINGS = "tveta_offerings.csv"

# Levels to scrape.  Override via --levels argument.
DEFAULT_LEVELS = {
    "artisan", "craft",
    "level 3", "level 4", "level 5",
    "short course", "trade test", "proficiency", "certificate",
}

# Only keep institutions with these status strings (case-insensitive).
ACTIVE_STATUSES = {"registered and licensed", "registered & licensed"}

DELAY_SECONDS = 1.0   # polite delay between requests
TIMEOUT       = 20    # seconds per request

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; KUCCPSS-scraper/1.0; "
        "+https://github.com/example/kuccpss)"
    ),
}


# ─── Minimal HTML table parser ───────────────────────────────────────────────

class TableParser(HTMLParser):
    """Extracts all <table> rows as lists of cell text."""

    def __init__(self):
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._in_table = False
        self._current_table: list[list[str]] = []
        self._current_row: list[str] = []
        self._current_cell: list[str] = []
        self._in_cell = False
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            if self._depth == 0:
                self._current_table = []
            self._depth += 1
        elif tag in ("tr",) and self._depth == 1:
            self._current_row = []
        elif tag in ("td", "th") and self._depth == 1:
            self._current_cell = []
            self._in_cell = True

    def handle_endtag(self, tag):
        if tag == "table":
            self._depth -= 1
            if self._depth == 0:
                self.tables.append(self._current_table)
        elif tag == "tr" and self._depth == 1:
            if self._current_row:
                self._current_table.append(self._current_row)
        elif tag in ("td", "th") and self._depth == 1:
            self._current_row.append(
                html.unescape(" ".join(self._current_cell).strip())
            )
            self._in_cell = False

    def handle_data(self, data):
        if self._in_cell:
            self._current_cell.append(data.strip())


class LinkParser(HTMLParser):
    """Extracts href values whose text matches a pattern."""

    def __init__(self, text_pattern: re.Pattern):
        super().__init__()
        self.links: list[str] = []
        self._pattern = text_pattern
        self._current_href: str | None = None
        self._collecting = False

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attrs_dict = dict(attrs)
            self._current_href = attrs_dict.get("href", "")
            self._collecting = False

    def handle_data(self, data):
        if self._current_href is not None and self._pattern.search(data):
            self._collecting = True

    def handle_endtag(self, tag):
        if tag == "a" and self._collecting:
            self.links.append(self._current_href)
            self._current_href = None
            self._collecting = False


# ─── Fetch helpers ───────────────────────────────────────────────────────────

def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} for {url}", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"  Error fetching {url}: {e}", file=sys.stderr)
        return ""


# ─── Scrape course list ───────────────────────────────────────────────────────

def scrape_course_list(levels_filter: set[str]) -> list[dict]:
    """
    Parses the TVETA courses page.
    Table columns: S/N | Course Name | Level | Exam Body | Action
    The Action cell contains a link like:
      /course/?course_id=KNC114
    We extract the course_id from <a href> tags in the raw HTML.
    """
    print(f"Fetching course list from {COURSES_URL} …")
    body = fetch(COURSES_URL)
    if not body:
        return []

    # Extract all href values for course detail links
    href_map: dict[str, str] = {}  # position_in_body → course_id
    for m in re.finditer(r'href=["\'](?:https?://[^"\']*)?/course/\?course_id=([A-Z0-9]+)["\']', body):
        href_map[m.start()] = m.group(1)

    if not href_map:
        return []

    # Parse table rows; pair each row with the nearest course_id link
    parser = TableParser()
    parser.feed(body)

    # We'll rebuild by scanning the raw HTML for table rows with course links
    # Simpler: use regex to find each <tr> block that contains a course link
    row_pattern = re.compile(
        r'<tr[^>]*>(.*?)</tr>',
        re.DOTALL | re.IGNORECASE,
    )
    td_pattern  = re.compile(r'<t[dh][^>]*>(.*?)</t[dh]>', re.DOTALL | re.IGNORECASE)
    tag_strip   = re.compile(r'<[^>]+>')

    courses = []
    for row_m in row_pattern.finditer(body):
        row_html = row_m.group(1)

        # Check if this row has a course_id link
        link_m = re.search(r'course_id=([A-Z0-9]+)', row_html)
        if not link_m:
            continue
        course_id = link_m.group(1)

        # Extract cell text
        cells = [
            html.unescape(tag_strip.sub(" ", c.group(1)).strip())
            for c in td_pattern.finditer(row_html)
        ]

        # Expected: S/N | Course Name | Level | Exam Body | Action
        if len(cells) < 3:
            continue
        name  = cells[1].strip() if len(cells) > 1 else ""
        level = cells[2].strip() if len(cells) > 2 else ""
        exam  = cells[3].strip() if len(cells) > 3 else ""

        if not name or name.lower() in ("course name", "s/n"):
            continue
        if level.lower() not in levels_filter:
            continue

        courses.append({
            "id":        course_id,
            "name":      name,
            "level":     level,
            "exam_body": exam,
        })

    return courses


# ─── Scrape institutions for one course ──────────────────────────────────────

def scrape_institutions(course_id: str) -> list[dict]:
    """
    Returns list of: {name, county, status}
    Only includes rows with status "Registered and Licensed".

    TVETA institution table columns (0-indexed):
      0: S/N  1: NAME  2: REG. NUMBER  3: CATEGORY  4: TYPE
      5: COUNTY  6: EXPIRY DATE  7: STATUS  8: ACTION
    """
    url  = f"{COURSE_URL}{course_id}"
    body = fetch(url)
    if not body:
        return []

    parser = TableParser()
    parser.feed(body)

    institutions = []
    for table in parser.tables:
        for row in table:
            # Need at least 8 columns for a full institution row
            if len(row) < 8:
                continue

            name   = row[1].strip()
            county = row[5].strip()
            status = row[7].strip()

            # Skip header rows
            if not name or name.upper() in ("NAME", "S/N", "#"):
                continue
            # Only keep active registrations
            if status.lower() not in ACTIVE_STATUSES:
                continue

            institutions.append({
                "name":   name,
                "county": county,
                "status": status,
            })

    return institutions


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    # Parse --levels argument
    levels_filter = DEFAULT_LEVELS
    if "--levels" in sys.argv:
        idx = sys.argv.index("--levels")
        custom = [a.lower() for a in sys.argv[idx + 1:] if not a.startswith("-")]
        if custom:
            levels_filter = set(custom)

    print(f"Levels to scrape: {sorted(levels_filter)}")

    # Step 1 — course list
    # Because the TVETA page uses JS-rendered tables, we embed the known IDs
    # as a fallback and also attempt live scraping.
    courses = scrape_course_list(levels_filter)

    if not courses:
        print("Live scrape returned no courses — using embedded course list.")
        courses = EMBEDDED_COURSES

    # Filter by requested levels
    courses = [c for c in courses if c["level"].lower() in levels_filter]
    print(f"Courses to process: {len(courses)}")

    # Write courses CSV
    with open(OUTPUT_COURSES, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["tveta_course_id", "tveta_course_name",
                                          "tveta_level", "exam_body"])
        w.writeheader()
        for c in courses:
            w.writerow({
                "tveta_course_id":   c["id"],
                "tveta_course_name": c["name"],
                "tveta_level":       c["level"],
                "exam_body":         c["exam_body"],
            })
    print(f"Wrote {len(courses)} courses to {OUTPUT_COURSES}")

    # Step 2 — institution pages
    total_rows = 0
    with open(OUTPUT_OFFERINGS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "tveta_course_id", "tveta_course_name", "tveta_level",
            "institution_name", "county", "status",
        ])
        w.writeheader()

        for i, course in enumerate(courses, 1):
            print(f"  [{i}/{len(courses)}] {course['id']} — {course['name']}")
            insts = scrape_institutions(course["id"])

            for inst in insts:
                w.writerow({
                    "tveta_course_id":   course["id"],
                    "tveta_course_name": course["name"],
                    "tveta_level":       course["level"],
                    "institution_name":  inst["name"],
                    "county":            inst["county"],
                    "status":            inst["status"],
                })
            total_rows += len(insts)
            print(f"      → {len(insts)} active institutions")
            time.sleep(DELAY_SECONDS)

    print(f"\nDone. {total_rows} offering rows written to {OUTPUT_OFFERINGS}")


# ─── Embedded course list (fallback if live scrape fails) ────────────────────
# These are the KNEC-examined Artisan and Craft courses confirmed from TVETA.
# Level 3/4/5 (CDACC-based) IDs are included for national polytechnics.

EMBEDDED_COURSES = [
    # ── ARTISAN (KNEC) ────────────────────────────────────────────────────────
    {"id": "KNC114", "name": "Agricultural Mechanics",                   "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC115", "name": "Appropriate Carpentry and Joinery",        "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC116", "name": "Building Technology",                      "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC117", "name": "Clerk-Typist",                             "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC118", "name": "Electrical and Electronics Technology",    "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC119", "name": "Electrical Installation",                  "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC120", "name": "Fashion Design and Garment Making",        "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC121", "name": "Food and Beverage",                        "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC122", "name": "Food Processing Technology",               "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC124", "name": "General Agriculture",                      "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC125", "name": "General Fitter",                           "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC126", "name": "Hairdressing and Beauty Therapy",          "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC127", "name": "Information Communication Technology",     "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC128", "name": "Leather Work",                             "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC129", "name": "Masonry",                                  "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC130", "name": "Mechanical Engineering (Plant Option)",    "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC131", "name": "Metal Processing Technology",              "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC132", "name": "Motor Vehicle Mechanics",                  "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC133", "name": "Motor Vehicle Technology",                 "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC134", "name": "Painting and Decoration",                  "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC135", "name": "Plumbing",                                 "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC136", "name": "Refrigeration and Air Conditioning Technology", "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC137", "name": "Salesmanship",                             "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC138", "name": "Seafarers",                                "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC139", "name": "Storekeeping",                             "level": "Artisan", "exam_body": "KNEC"},
    {"id": "KNC140", "name": "Welding and Fabrication",                  "level": "Artisan", "exam_body": "KNEC"},
    # ── CRAFT (KNEC) ─────────────────────────────────────────────────────────
    {"id": "KSB102", "name": "Accounting and Management Skills",         "level": "Craft", "exam_body": "KASNEB"},
    {"id": "KSB103", "name": "Information Communication Technology",     "level": "Craft", "exam_body": "KASNEB"},
    {"id": "KWS102", "name": "Aquaculture",                              "level": "Craft", "exam_body": "KWS"},
    {"id": "KWS103", "name": "Community Wildlife Management",            "level": "Craft", "exam_body": "KWS"},
    {"id": "KWS104", "name": "Nature Interpretation and Tour Administration", "level": "Craft", "exam_body": "KWS"},
    {"id": "KNC141", "name": "Accountancy",                              "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC142", "name": "Agricultural Engineering (Farm Power and Machinery)", "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC143", "name": "Agricultural Mechanics",                   "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC144", "name": "Automotive Engineering",                   "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC145", "name": "Baking Technology",                        "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC146", "name": "Banking and Finance",                      "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC147", "name": "Building Technology",                      "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC148", "name": "Business Administration",                  "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC149", "name": "Business Management",                      "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC150", "name": "Carpentry and Joinery",                    "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC151", "name": "Cartography",                              "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC152", "name": "Catering and Accommodation Operations",    "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC153", "name": "Child Care and Protection",                "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC154", "name": "Clerical Operations",                      "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC155", "name": "Construction Plant Technology",            "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC156", "name": "Co-operative Management",                  "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC157", "name": "Electrical and Electronics Technology",    "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC158", "name": "Electrical and Electronics Technology (Power)", "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC159", "name": "Electrical and Electronics Technology (Telecommunication)", "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC160", "name": "Electrical Installation",                  "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC161", "name": "Fashion Design and Garment Making",        "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC162", "name": "Fisheries Science and Technology",         "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC163", "name": "Food and Beverage Production and Service", "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC164", "name": "Food Processing and Preservation",         "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC165", "name": "Food Processing and Preservation Technology", "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC166", "name": "Food Processing Technology",               "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC168", "name": "General Agriculture",                      "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC169", "name": "Housekeeping and Laundry",                 "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC170", "name": "Human Resource Management",                "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC171", "name": "Information Communication Technology",     "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC172", "name": "Information Studies",                      "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC173", "name": "Information Technology",                   "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC174", "name": "Investment Management",                    "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC175", "name": "Land Surveying",                           "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC176", "name": "Library, Archives and Information Studies","level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC177", "name": "Marine Engineering",                       "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC178", "name": "Maritime Transport Logistics",             "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC179", "name": "Maritime Transport Operations",            "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC180", "name": "Marketing",                                "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC181", "name": "Masonry",                                  "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC182", "name": "Mechanical Engineering",                   "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC183", "name": "Mechanical Engineering (Construction)",    "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC184", "name": "Mechanical Engineering (Plant)",           "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC185", "name": "Mechanical Engineering (Production)",      "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC186", "name": "Medical Laboratory Technology",            "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC187", "name": "Motor Vehicle Mechanics",                  "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC188", "name": "Motor Vehicle Technology",                 "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC189", "name": "Social Development",                       "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC190", "name": "Nautical Science",                         "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC192", "name": "Nutrition and Dietetics",                  "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC193", "name": "Personnel Management",                     "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC194", "name": "Petroleum Geosciences",                    "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC195", "name": "Photogrammetry",                           "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC196", "name": "Plumbing",                                 "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC197", "name": "Printing Technology",                      "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC198", "name": "Project Management",                       "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC199", "name": "Radio Servicing",                          "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC200", "name": "Road Construction",                        "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC201", "name": "Road Transport Management",                "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC202", "name": "Sales and Marketing",                      "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC203", "name": "Science Laboratory Technology",            "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC204", "name": "Secretarial Studies",                      "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC205", "name": "Social Work and Community Development",    "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC206", "name": "Supplies Management",                      "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC207", "name": "Supply Chain Management",                  "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC208", "name": "Tannery and Leatherwork",                  "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC209", "name": "Tour Guiding and Travel Operations",       "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC210", "name": "Tour Guiding Operations",                  "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC211", "name": "Transport Management",                     "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC212", "name": "Water Engineering",                        "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC213", "name": "Water Technology",                         "level": "Craft", "exam_body": "KNEC"},
    {"id": "KNC214", "name": "Welding and Fabrication",                  "level": "Craft", "exam_body": "KNEC"},
    # ── LEVEL 5 (National Polytechnics + Specialised) ─────────────────────────
    {"id": "HRM102",   "name": "Human Resource Management",              "level": "Level 5", "exam_body": "HRM"},
    {"id": "KRCT102",  "name": "Advanced Emergency Medical Technician",  "level": "Level 5", "exam_body": "KRCT"},
    {"id": "KWS101",   "name": "Paramilitary and Wildlife Law Enforcement", "level": "Level 5", "exam_body": "KWS"},
    {"id": "KTLNP105", "name": "Electrical Installation",                "level": "Level 5", "exam_body": "KTLNP"},
    {"id": "KTLNP106", "name": "Food Processing",                        "level": "Level 5", "exam_body": "KTLNP"},
    {"id": "KTLNP108", "name": "Health Records",                         "level": "Level 5", "exam_body": "KTLNP"},
    {"id": "KTLNP110", "name": "Information Communication Technology",   "level": "Level 5", "exam_body": "KTLNP"},
    {"id": "KTLNP114", "name": "Motor Vehicle Body Repair",              "level": "Level 5", "exam_body": "KTLNP"},
    {"id": "KTLNP117", "name": "Plumbing",                               "level": "Level 5", "exam_body": "KTLNP"},
    {"id": "KTLNP120", "name": "Solar Installation",                     "level": "Level 5", "exam_body": "KTLNP"},
    {"id": "KTLNP121", "name": "Tour and Travel Operations",             "level": "Level 5", "exam_body": "KTLNP"},
    {"id": "KTLNP124", "name": "Welding and Fabrication",                "level": "Level 5", "exam_body": "KTLNP"},
    {"id": "MMUST108", "name": "Sports Coaching",                        "level": "Level 5", "exam_body": "MMUST"},
    {"id": "MMUST110", "name": "Social Work and Community Development",  "level": "Level 5", "exam_body": "MMUST"},
    {"id": "MMUST111", "name": "Mortuary Science",                       "level": "Level 5", "exam_body": "MMUST"},
    {"id": "MMUST114", "name": "Criminology and Criminal Justice",       "level": "Level 5", "exam_body": "MMUST"},
    {"id": "MMUST118", "name": "General Agriculture",                    "level": "Level 5", "exam_body": "MMUST"},
    {"id": "NYANP101", "name": "Automotive Technology",                  "level": "Level 5", "exam_body": "NYANP"},
    {"id": "NYANP111", "name": "Electrical Technology",                  "level": "Level 5", "exam_body": "NYANP"},
    {"id": "NYANP115", "name": "Fire Fighting Technology",               "level": "Level 5", "exam_body": "NYANP"},
    {"id": "NYANP116", "name": "Food Processing",                        "level": "Level 5", "exam_body": "NYANP"},
    {"id": "NYANP121", "name": "Science Laboratory Practice",            "level": "Level 5", "exam_body": "NYANP"},
    {"id": "NYANP123", "name": "Solar PV",                               "level": "Level 5", "exam_body": "NYANP"},
    {"id": "TUM117",   "name": "Building and Civil Engineering",         "level": "Level 5", "exam_body": "TUM"},
    {"id": "TUM118",   "name": "Community Health",                       "level": "Level 5", "exam_body": "TUM"},
    {"id": "TUM119",   "name": "Information Communication Technology",   "level": "Level 5", "exam_body": "TUM"},
    {"id": "ELNP102",  "name": "General Agriculture",                    "level": "Level 5", "exam_body": "ELNP"},
    {"id": "ELNP105",  "name": "Beauty Therapy",                         "level": "Level 5", "exam_body": "ELNP"},
    {"id": "ELNP111",  "name": "Hair Dressing",                          "level": "Level 5", "exam_body": "ELNP"},
    {"id": "ELNP143",  "name": "Cosmetology",                            "level": "Level 5", "exam_body": "ELNP"},
    {"id": "ELNP144",  "name": "Motorcycle Mechanics",                   "level": "Level 5", "exam_body": "ELNP"},
    {"id": "ELNP145",  "name": "Road Construction",                      "level": "Level 5", "exam_body": "ELNP"},
    {"id": "ELNP146",  "name": "Science Laboratory Technology",          "level": "Level 5", "exam_body": "ELNP"},
    {"id": "KCNP106",  "name": "Marine Welding and Fabrication",         "level": "Level 5", "exam_body": "KCNP"},
    {"id": "KCNP110",  "name": "Human Resource Management",              "level": "Level 5", "exam_body": "KCNP"},
    {"id": "KSINP102", "name": "Animal Health and Production",           "level": "Level 5", "exam_body": "KSINP"},
    {"id": "KSINP104", "name": "Carpentry Technology",                   "level": "Level 5", "exam_body": "KSINP"},
    {"id": "KSINP106", "name": "Community Health",                       "level": "Level 5", "exam_body": "KSINP"},
    {"id": "KSINP110", "name": "Dairy Plant Technology",                 "level": "Level 5", "exam_body": "KSINP"},
    {"id": "KSINP113", "name": "Food Processing Technology",             "level": "Level 5", "exam_body": "KSINP"},
    {"id": "KSINP121", "name": "Masonry",                                "level": "Level 5", "exam_body": "KSINP"},
    {"id": "KSINP122", "name": "Medical Engineering Technology",         "level": "Level 5", "exam_body": "KSINP"},
    {"id": "KSINP125", "name": "Horticulture Production",                "level": "Level 5", "exam_body": "KSINP"},
    {"id": "KSMNP101", "name": "Spinning Machine Maintenance Technician","level": "Level 5", "exam_body": "KSMNP"},
    {"id": "KSMNP104", "name": "Weaving Machine Maintenance Technology", "level": "Level 5", "exam_body": "KSMNP"},
    {"id": "KSMNP113", "name": "Electrical Security System Technician",  "level": "Level 5", "exam_body": "KSMNP"},
    {"id": "KSMNP114", "name": "Electrical Solar Installation Technician","level": "Level 5", "exam_body": "KSMNP"},
    {"id": "KSMNP120", "name": "Fashion and Apparel Design",             "level": "Level 5", "exam_body": "KSMNP"},
    {"id": "KSMNP124", "name": "Hair Dressing Operations Technology",    "level": "Level 5", "exam_body": "KSMNP"},
    {"id": "KSMNP126", "name": "Information and Communication Technology","level": "Level 5", "exam_body": "KSMNP"},
    {"id": "KSMNP129", "name": "Masonry",                                "level": "Level 5", "exam_body": "KSMNP"},
    {"id": "KSMNP131", "name": "Plumbing",                               "level": "Level 5", "exam_body": "KSMNP"},
    {"id": "KSMNP133", "name": "Science Laboratory Technology with Instrumentation", "level": "Level 5", "exam_body": "KSMNP"},
    {"id": "KSMNP139", "name": "Aquaculture Technology",                 "level": "Level 5", "exam_body": "KSMNP"},
    {"id": "KSMNP142", "name": "Fisheries Technology",                   "level": "Level 5", "exam_body": "KSMNP"},
    {"id": "MRNP101",  "name": "Agricultural Extension Technology",      "level": "Level 5", "exam_body": "MRNP"},
    {"id": "MRNP103",  "name": "Building Technology",                    "level": "Level 5", "exam_body": "MRNP"},
    {"id": "MRNP106",  "name": "Data Communication and Computer Network Technician", "level": "Level 5", "exam_body": "MRNP"},
    {"id": "NYNP102",  "name": "Science Laboratory Technology",          "level": "Level 5", "exam_body": "NYNP"},
    {"id": "NYNP104",  "name": "Automotive Technology",                  "level": "Level 5", "exam_body": "NYNP"},
    {"id": "NYNP107",  "name": "Electrical Operation (Power Option)",    "level": "Level 5", "exam_body": "NYNP"},
    {"id": "NYNP109",  "name": "Fashion Design Operation",               "level": "Level 5", "exam_body": "NYNP"},
    {"id": "NYNP112",  "name": "Mechanical Production Technology",       "level": "Level 5", "exam_body": "NYNP"},
    {"id": "NYNP113",  "name": "Plumbing",                               "level": "Level 5", "exam_body": "NYNP"},
    {"id": "NYNP115",  "name": "Tourism Management",                     "level": "Level 5", "exam_body": "NYNP"},
    {"id": "NYNP117",  "name": "Information Communication Technology",   "level": "Level 5", "exam_body": "NYNP"},
    {"id": "NYNP119",  "name": "Business Management",                    "level": "Level 5", "exam_body": "NYNP"},
    {"id": "NYNP120",  "name": "Electrical and Electronic Engineering Technology", "level": "Level 5", "exam_body": "NYNP"},
    {"id": "NYNP129",  "name": "Cooperative Management",                 "level": "Level 5", "exam_body": "NYNP"},
    {"id": "NYNP131",  "name": "Front Office Operation",                 "level": "Level 5", "exam_body": "NYNP"},
    {"id": "NYNP133",  "name": "Office Administration",                  "level": "Level 5", "exam_body": "NYNP"},
    {"id": "NYNP138",  "name": "Food Processing Technology",             "level": "Level 5", "exam_body": "NYNP"},
    {"id": "NYNP141",  "name": "Building Technology",                    "level": "Level 5", "exam_body": "NYNP"},
    {"id": "NYNP153",  "name": "Cosmetology",                            "level": "Level 5", "exam_body": "NYNP"},
    {"id": "NYNP160",  "name": "Food and Beverage",                      "level": "Level 5", "exam_body": "NYNP"},
    {"id": "NYNP163",  "name": "Tour Guide",                             "level": "Level 5", "exam_body": "NYNP"},
    {"id": "NYNP164",  "name": "Tour Operation",                         "level": "Level 5", "exam_body": "NYNP"},
    {"id": "NYNP168",  "name": "Record Management",                      "level": "Level 5", "exam_body": "NYNP"},
    {"id": "NYNP170",  "name": "Social Work and Community Development",  "level": "Level 5", "exam_body": "NYNP"},
    {"id": "NYNP171",  "name": "Automotive Mechatronics Technology",     "level": "Level 5", "exam_body": "NYNP"},
    {"id": "NYNP185",  "name": "Welding and Fabrication",                "level": "Level 5", "exam_body": "NYNP"},
]


if __name__ == "__main__":
    main()
