import json

with open('data/tvet_clean_offerings.json', encoding='utf-8') as f:
    data = json.load(f)

lines = ['OFFERINGS = [']
for o in data['offerings']:
    prog = o['programme'].replace("'", "\\'")
    inst = o['institution'].replace("'", "\\'")
    lines.append(f"    ('{o['code']}', '{inst}', '{prog}'),")
lines.append(']')

with open('data/tvet_offerings_output.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f"Written {len(data['offerings'])} offerings")
