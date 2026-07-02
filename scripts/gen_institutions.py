"""
Generate the INSTITUTIONS list for seed_tvet.py.
"""
import json, re

with open('data/tvet_clean_offerings.json', encoding='utf-8') as f:
    data = json.load(f)

inst_names = sorted(set(o['institution'] for o in data['offerings']))

# Exclude teacher training colleges
EXCLUDE = {
    'Kagumo Teachers Training College',
    'Kibabii Diploma Teachers Training College',
    'Lugari Diploma Teachers Training College',
    'Kibabii University',  # not a TVET institution per se
}

# Known private institutions
PRIVATE = {
    'Friends College Kaimosi',
    'Heroes Technical And Vocational College',
    'Total Technical And Vocational College',
}

# Manual location overrides (where name doesn't reveal location clearly)
LOCATION_OVERRIDES = {
    'Ahmed Shahame Mwidani Technical Training Institute': 'Mombasa',
    'Bandari Maritime Academy': 'Mombasa',
    'Bukura Agricultural College': 'Kakamega',
    'Centre For Tourism Training And Research': 'Nairobi',
    'East African School Of Aviation': 'Nairobi',
    'Kenya Coast Polytechnic': 'Mombasa',
    'Kenya Forestry College': 'Londiani',
    'Kenya Industrial Training Institute': 'Nairobi',
    'Kenya Institute Of Highways And Building Technology': 'Nairobi',
    'Kenya Institute Of Mass Communication': 'Nairobi',
    'Kenya Institute Of Surveying And Mapping': 'Nairobi',
    'Kenya School Of Agriculture': 'Kabete',
    'Kenya School Of Revenue Administration': 'Nairobi',
    'Kenya Water Institute': 'Nairobi',
    'Kenya Wildlife Service Training Institute': 'Naivasha',
    'Morendat Institute Of Oil And Gas': 'Naivasha',
    'Railway Training Institute': 'Nairobi',
    'Regional Centre For Mapping Of Resources For Development': 'Nairobi',
    'Ramogi Institute Of Advance Technology': 'Kisumu',
    'Siaya Institute Of Technology': 'Siaya',
    'The Cuk Nairobi Cbd Training Institute': 'Nairobi',
    'Friends College Kaimosi': 'Vihiga',
    'Pc Kinyanjui Technical Training Institute': 'Nairobi',
    'Jaramogi Oginga Odinga University Of Science And Technology': 'Bondo',
    'Jomo Kenyatta University Of Agriculture And Technology Tvet Institute': 'Juja',
    'Machakos University': 'Machakos',
    'Masinde Muliro University Of Science & Technology': 'Kakamega',
    'Multimedia University Of Kenya': 'Nairobi',
    'Pwani University': 'Kilifi',
    'Rongo University': 'Migori',
    'South Eastern Kenya University': 'Kitui',
    'Technical University Of Kenya': 'Nairobi',
    'Technical University Of Mombasa': 'Mombasa',
    'Tharaka University': 'Tharaka',
    'Turkana University College': 'Lodwar',
    'Laikipia University': 'Nyahururu',
    'Meru University Of Science And Technology': 'Meru',
    'Alupe University Tvet Institute': 'Busia',
    'Laikipia University Tvet Institute': 'Nyahururu',
    'Tharaka University Tvet Institute': 'Tharaka',
    'The University Of Embu Tvet Institute': 'Embu',
    'Seku Directorate Of Tvet Wote Campus': 'Makueni',
    'North Eastern National Polytechnic': 'Garissa',
    'Eldoret Polytechnic': 'Eldoret',
    'Masai Technical Training Institute': 'Kajiado',
    'Maasai Mara Technical Vocational College': 'Narok',
    'Rift Valley Institute Of Science And Technology': 'Nakuru',
    'Karen Technical Training Institute For The Deaf': 'Nairobi',
    'Machakos Technical Institute For The Blind': 'Machakos',
    'Sikri Technical Training Institute For The Blind And Deaf': 'Bungoma',
}

# Manual abbreviation overrides
ABBREV_OVERRIDES = {
    'Kabete National Polytechnic': 'KNP',
    'Kisii National Polytechnic': 'KisiNP',
    'Kisumu Polytechnic': 'KisuPoly',
    'Kitale National Polytechnic': 'KiNP',
    'Meru National Polytechnic': 'MNP',
    'Nairobi Technical Training Institute': 'NTTI',
    'Sigalagala National Polytechnic': 'SNP',
    'Eldoret Polytechnic': 'EP',
    'Nyeri National Polytechnic': 'NNP',
    'North Eastern National Polytechnic': 'NENP',
    'Nyandarua National Polytechnic': 'NyNP',
    'Pc Kinyanjui Technical Training Institute': 'PCKTTI',
    'Kenya Industrial Training Institute': 'KITI',
    'Kenya Institute Of Highways And Building Technology': 'KIHBT',
    'Kenya Institute Of Mass Communication': 'KIMC',
    'Kenya Institute Of Surveying And Mapping': 'KISM',
    'Kenya Forestry College': 'KFC',
    'Kenya School Of Agriculture': 'KSA',
    'Kenya School Of Revenue Administration': 'KESRA',
    'Kenya Water Institute': 'KEWI',
    'Kenya Wildlife Service Training Institute': 'KWSTI',
    'Kenya Coast Polytechnic': 'KCP',
    'East African School Of Aviation': 'EASA',
    'Bandari Maritime Academy': 'BMA',
    'Railway Training Institute': 'RTI',
    'Centre For Tourism Training And Research': 'CTTR',
    'Regional Centre For Mapping Of Resources For Development': 'RCMRD',
    'Morendat Institute Of Oil And Gas': 'MIOG',
    'Ramogi Institute Of Advance Technology': 'RIAT',
    'Siaya Institute Of Technology': 'SIT',
    'Technical University Of Kenya': 'TUK',
    'Technical University Of Mombasa': 'TUM',
    'Bukura Agricultural College': 'BAC',
    'Coast Institute Of Technology': 'CIT',
    'Rift Valley Institute Of Science And Technology': 'RVIST',
    'Rift Valley Technical Training Institute': 'RVTTI',
    'Friends College Kaimosi': 'FCK',
}

def derive_abbrev(name):
    # Try overrides first
    if name in ABBREV_OVERRIDES:
        return ABBREV_OVERRIDES[name]
    # Abbreviate by taking first letter of each significant word
    stop = {'of', 'and', 'the', 'for', 'in', 'at', 'de', 'le', '&'}
    words = re.findall(r"[A-Za-z']+", name)
    letters = [w[0].upper() for w in words if w.lower() not in stop]
    return ''.join(letters[:6])

def derive_location(name):
    if name in LOCATION_OVERRIDES:
        return LOCATION_OVERRIDES[name]
    suffixes = [
        'Technical And Vocational College', 'Technical & Vocational College',
        'Technical Vocational College', 'Technical Training Institute',
        'National Polytechnic', 'Polytechnic',
        'Technical College', 'Technical Institute',
        'Institute Of Science And Technology', 'Institute Of Technology',
        'University Of Science And Technology', 'University Of Science & Technology',
        'University College', 'University Tvet Institute',
        'Tvet Institute', 'University',
        'Agricultural College', 'Technical & Vocational College',
    ]
    n = name
    for suf in suffixes:
        if n.endswith(suf):
            loc = n[:-len(suf)].strip(' &-')
            # Clean up "North/South/East/West" prefixes for some
            return loc if loc else name
    return name

print('INSTITUTIONS = [')
for name in inst_names:
    if name in EXCLUDE:
        continue
    loc = derive_location(name)
    abbrev = derive_abbrev(name)
    is_pub = name not in PRIVATE
    is_pub_str = 'True' if is_pub else 'False'
    print(f"    ('{name}', '{loc}', '{abbrev}', {is_pub_str}),")
print(']')
print(f'\n# Total: {sum(1 for n in inst_names if n not in EXCLUDE)} institutions')
