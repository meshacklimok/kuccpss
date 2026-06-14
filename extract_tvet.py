import pypdf, re, json

r = pypdf.PdfReader('DIPLOMA_PROGRAMMES.pdf')
offerings = []

for page in r.pages:
    text = page.extract_text()
    if not text:
        continue
    for line in text.split('\n'):
        line = line.strip()
        if not line or line.startswith('No.'):
            continue
        m = re.match(
            r'^\d+\s+(\d{7})\s+([A-Z][A-Z\s&()\-\/\.]+?)\s+(DIPLOMA|CERTIFICATE|ARTISAN|CRAFT)\s+IN\s+(.+?)\s+([\d,]+)\s*$',
            line
        )
        if m:
            prog_code = m.group(1).strip()
            institution = m.group(2).strip().title()
            level = m.group(3).strip().title()
            programme = (level + ' In ' + m.group(4).strip()).title()
            offerings.append({'code': prog_code, 'institution': institution, 'programme': programme})

print(f'Total offerings extracted: {len(offerings)}')

institutions = sorted(set(o['institution'] for o in offerings))
programmes = sorted(set(o['programme'] for o in offerings))
print(f'Unique institutions: {len(institutions)}')
print(f'Unique programmes: {len(programmes)}')

with open('tvet_raw_data.json', 'w', encoding='utf-8') as f:
    json.dump({'offerings': offerings, 'institutions': institutions, 'programmes': programmes}, f, indent=2)

print('Saved to tvet_raw_data.json')
print('\nSample offerings:')
for o in offerings[:5]:
    print(o)
