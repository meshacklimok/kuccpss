"""Read-only scrape of https://students.kuccps.net/programmes/ degree clusters 1-18.
Caches every page under .cache/kuccps_portal/ (delete it to re-fetch), writes
data/kuccps_portal_degrees.json for `manage.py import_kuccps_portal`. Resumable, 1 req/s.

    python scripts/scrape_kuccps_portal.py"""
import html, json, os, re, time, urllib.request

BASE = "https://students.kuccps.net"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = os.path.join(ROOT, ".cache", "kuccps_portal")
OUT = os.path.join(ROOT, "data", "kuccps_portal_degrees.json")
NUM_CLUSTERS = 18
os.makedirs(PAGES, exist_ok=True)


def fetch(path, cache_name):
    fp = os.path.join(PAGES, cache_name)
    if os.path.exists(fp) and os.path.getsize(fp) > 1000:
        return open(fp, encoding="utf-8", errors="ignore").read()
    for attempt in range(4):
        try:
            req = urllib.request.Request(BASE + path, headers={"User-Agent": "Mozilla/5.0"})
            body = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "ignore")
            open(fp, "w", encoding="utf-8").write(body)
            time.sleep(1)
            return body
        except Exception as e:
            print("  retry", path, e, flush=True)
            time.sleep(5 * (attempt + 1))
    return ""


def text(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def codes(cell):
    seen = []
    for c in text(cell).split("/"):
        c = c.strip().upper()
        if c and c not in seen:
            seen.append(c)
    return seen


def parse_detail(s):
    out = {}
    m = re.search(r'btn-outline btn-danger[^>]*>([^<]+)<', s)
    out["cluster_label"] = text(m.group(1)) if m else ""
    m = re.search(r'<h\d[^>]*>\s*([^<]*BACHELOR[^<]*|[^<]+)</h\d>\s*<div class="btn-group', s)

    def section(title):
        i = s.find(title)
        if i < 0:
            return ""
        j = s.find("</table>", i)
        return s[i:j]

    entry = []
    for th, td in re.findall(r'<th[^>]*>\s*(Cluster Subject \d+)\s*</th>\s*<td[^>]*>(.*?)</td>',
                             section("Minimum Entry Requirements"), re.S):
        entry.append({"slot": int(th.split()[-1]), "subjects": codes(td)})
    out["cluster_subjects"] = entry

    subj = []
    for th, td, grade in re.findall(
            r'<th[^>]*>\s*(Subject \d+)\s*</th>\s*<td[^>]*>(.*?)</td\s*>\s*<td[^>]*>(.*?)</td>',
            section("Minimum Subject Requirements"), re.S):
        subj.append({"slot": int(th.split()[-1]), "subjects": codes(td), "min_grade": text(grade)})
    out["subject_requirements"] = subj

    i = s.find("Available Programmes")
    tbl = s[i:s.find("</table>", i)] if i >= 0 else ""
    years = re.findall(r'KCSE (\d{4}) Cut-off', tbl)
    offerings = []
    for row in re.findall(r'<tr class="text-uppercase">(.*?)</tr>', tbl, re.S):
        tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
        if len(tds) < 4:
            continue
        inst_cell = tds[0]
        county = re.search(r'<label[^>]*>(.*?)</label>', inst_cell, re.S)
        inst = text(re.sub(r'<label.*?</label>', '', inst_cell, flags=re.S))
        cut = {}
        for y, v in zip(years, tds[4:4 + len(years)]):
            v = text(v)
            try:
                cut[y] = float(v)
            except ValueError:
                pass
        offerings.append({
            "institution": inst,
            "county": text(county.group(1)) if county else "",
            "inst_type": text(tds[1]),
            "programme_code": text(tds[2]).split()[0] if text(tds[2]) else "",
            "programme_name": text(tds[3]),
            "cutoffs": cut,
        })
    out["cutoff_years"] = years
    out["offerings"] = offerings
    return out


def main():
    progs = {}
    for n in range(1, NUM_CLUSTERS + 1):
        s = fetch(f"/programmes/search/?group=cluster_{n}", f"cluster_{n}.html")
        for row in re.findall(r'<tr.*?</tr>', s, re.S):
            m = re.search(r'/programmes/detail/(\d+)/', row)
            tds = [text(c) for c in re.findall(r'<td.*?</td>', row, re.S)]
            if m and len(tds) >= 3:
                progs[m.group(1)] = {"id": m.group(1), "name": tds[1], "cluster_list_label": tds[2],
                                     "cluster_number": n}
    print("programmes:", len(progs), flush=True)
    for k, (pid, p) in enumerate(sorted(progs.items(), key=lambda x: int(x[0])), 1):
        s = fetch(f"/programmes/detail/{pid}/", f"detail_{pid}.html")
        if s:
            p.update(parse_detail(s))
        if k % 50 == 0:
            print(f"{k}/{len(progs)}", flush=True)
    json.dump(list(progs.values()), open(OUT, "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    print("done", flush=True)


if __name__ == "__main__":
    main()
