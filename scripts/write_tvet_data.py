import json

with open('data/tvet_clean_offerings.json', encoding='utf-8') as f:
    data = json.load(f)

EXTRA_CANONICAL = {
    'Diploma In Accountants Technicians Diploma': 'Diploma in Accountancy',
    'Diploma In Electrical & Electronic Engineering(Power)': 'Diploma in Electrical & Electronics Engineering (Power)',
    'Diploma In Food Science And Nutrition': 'Diploma in Food Science & Technology',
    'Diploma In Hospitality Management': 'Diploma in Tourism & Hospitality Management',
    'Diploma In Marketing': 'Diploma in Sales & Marketing',
    'Diploma In Pharmacy': 'Diploma in Pharmaceutical Technology',
}

clean = []
for o in data['offerings']:
    prog = EXTRA_CANONICAL.get(o['programme'], o['programme'])
    clean.append({'code': o['code'], 'institution': o['institution'], 'programme': prog})

print(f'Final offerings: {len(clean)}')
unique_progs = sorted(set(o['programme'] for o in clean))
print(f'Unique programmes: {len(unique_progs)}')

with open('courses/management/commands/tvet_data.json', 'w', encoding='utf-8') as f:
    json.dump(clean, f, separators=(',', ':'))

print('Written tvet_data.json')
