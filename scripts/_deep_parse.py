import re

with open("_kuccps_page.html", encoding="utf-8") as f:
    html = f.read()

# Look for any <tr> rows with actual programme data
rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
print(f"Total <tr> rows: {len(rows)}")
for i, row in enumerate(rows[:20]):
    cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.DOTALL)
    cells_clean = [re.sub(r"<[^>]+>","",c).strip() for c in cells]
    if any(c for c in cells_clean):
        print(f"Row {i}: {cells_clean}")

# Find the login URL
login = re.findall(r'href=["\']([^"\']*login[^"\']*)["\']', html, re.IGNORECASE)
print(f"\nLogin URLs: {login}")

# Find any form actions
forms = re.findall(r'<form[^>]*action=["\']([^"\']+)["\']', html, re.IGNORECASE)
print(f"Form actions: {forms}")

# Look for any data attributes containing programme info
data_attrs = re.findall(r'data-[a-z-]+=["\'](.*?)["\']', html)
relevant = [d for d in data_attrs if len(d) > 5 and not d.startswith("/assets")]
print(f"\nData attributes (first 20 relevant):")
for d in relevant[:20]:
    print(f"  {d}")
