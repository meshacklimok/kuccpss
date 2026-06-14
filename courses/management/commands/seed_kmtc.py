"""
Management command: seed_kmtc

Populates InstitutionType (KMTC), all KMTC campus Institution records,
CourseType (KMTC), all unique KMTC Course records with subject requirements,
and CourseOffering records (programme_code → campus link).

Data source: KMTC Programmes on KUCCPS Portal (342 entries, 34 programme types,
~80 campuses).

Usage:
    py -3.13 manage.py seed_kmtc
    py -3.13 manage.py seed_kmtc --clear   # wipe existing KMTC data first
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from institutions.models import Institution, InstitutionType
from courses.models import Course, CourseType, CourseOffering


# ─────────────────────────────────────────────────────────────
# 1.  UNIQUE PROGRAMMES  (key = K-number suffix)
# subject_requirements: list of {slot, subjects_str, min_grade}
# ─────────────────────────────────────────────────────────────
PROGRAMMES = {
    'K01': {
        'name': 'Diploma in Community Oral Health',
        'mean_grade': 'C',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',              'min_grade': 'C'},
            {'slot': 2, 'subjects_str': 'BIO/BSC',              'min_grade': 'C'},
            {'slot': 3, 'subjects_str': 'PHY/PSC/CHE/MAT A',    'min_grade': 'C-'},
            {'slot': 4, 'subjects_str': 'PHY/PSC/CHE/MAT A',    'min_grade': 'C'},
        ],
    },
    'K02': {
        'name': 'Diploma in Nutrition and Dietetics',
        'mean_grade': 'C-',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',                       'min_grade': 'D+'},
            {'slot': 2, 'subjects_str': 'BIO/BSC',                       'min_grade': 'D+'},
            {'slot': 3, 'subjects_str': 'CHE/PSC',                       'min_grade': 'D+'},
            {'slot': 4, 'subjects_str': 'MAT A/HSC/AGR/PHY/PSC/GSC',    'min_grade': 'D'},
        ],
    },
    'K03': {
        'name': 'Diploma in Health Records and Information Technology',
        'mean_grade': 'C',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',                                   'min_grade': 'C'},
            {'slot': 2, 'subjects_str': 'MAT A',                                      'min_grade': 'C-'},
            {'slot': 3, 'subjects_str': 'BIO/BSC',                                    'min_grade': 'D+'},
            {'slot': 4, 'subjects_str': 'PHY/PSC/CHE/CMP/AGR/HSC/ECON/GEO/COM/BST', 'min_grade': 'C-'},
        ],
    },
    'K04': {
        'name': 'Diploma in Kenya Registered Community Health Nursing',
        'mean_grade': 'C',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',           'min_grade': 'C'},
            {'slot': 2, 'subjects_str': 'BIO/BSC',           'min_grade': 'C'},
            {'slot': 3, 'subjects_str': 'PHY/PSC/CHE/MAT A', 'min_grade': 'C-'},
        ],
    },
    'K06': {
        'name': 'Diploma in Kenya Registered Nursing and Midwifery',
        'mean_grade': 'C',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',           'min_grade': 'C'},
            {'slot': 2, 'subjects_str': 'BIO/BSC',           'min_grade': 'C'},
            {'slot': 3, 'subjects_str': 'PHY/PSC/CHE/MAT A', 'min_grade': 'C-'},
        ],
    },
    'K07': {
        'name': 'Diploma in Radiography and Imaging',
        'mean_grade': 'C',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',     'min_grade': 'C'},
            {'slot': 2, 'subjects_str': 'BIO/BSC',     'min_grade': 'C'},
            {'slot': 3, 'subjects_str': 'PHY/PSC',     'min_grade': 'C'},
            {'slot': 4, 'subjects_str': 'CHE/MAT A',   'min_grade': 'C-'},
        ],
    },
    'K08': {
        'name': 'Diploma in Medical Laboratory Sciences',
        'mean_grade': 'C',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',        'min_grade': 'C'},
            {'slot': 2, 'subjects_str': 'BIO/BSC',        'min_grade': 'C'},
            {'slot': 3, 'subjects_str': 'CHE/PSC',        'min_grade': 'C'},
            {'slot': 4, 'subjects_str': 'PHY/PSC/MAT A',  'min_grade': 'C'},
        ],
    },
    'K09': {
        'name': 'Diploma in Occupational Therapy',
        'mean_grade': 'C',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',                   'min_grade': 'C'},
            {'slot': 2, 'subjects_str': 'BIO/BSC',                   'min_grade': 'C-'},
            {'slot': 3, 'subjects_str': 'PHY/PSC/CHE/MAT A/AGR/HSC', 'min_grade': 'C-'},
        ],
    },
    'K10': {
        'name': 'Diploma in Optometry',
        'mean_grade': 'C',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS', 'min_grade': 'C'},
            {'slot': 2, 'subjects_str': 'MAT A',   'min_grade': 'C'},
            {'slot': 3, 'subjects_str': 'BIO/BSC', 'min_grade': 'C-'},
            {'slot': 4, 'subjects_str': 'PHY/PSC', 'min_grade': 'C-'},
        ],
    },
    'K11': {
        'name': 'Diploma in Orthopaedic Technology',
        'mean_grade': 'C',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',                   'min_grade': 'C'},
            {'slot': 2, 'subjects_str': 'BIO/BSC',                   'min_grade': 'C'},
            {'slot': 3, 'subjects_str': 'MAT A/PHY/CHE/PSC/WW/MW/DRD', 'min_grade': 'C-'},
            {'slot': 4, 'subjects_str': 'MAT A/PHY/CHE/PSC/WW/MW/DRD', 'min_grade': 'C-'},
        ],
    },
    'K12': {
        'name': 'Diploma in Pharmacy',
        'mean_grade': 'C',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',       'min_grade': 'C'},
            {'slot': 2, 'subjects_str': 'CHE/PSC',       'min_grade': 'C'},
            {'slot': 3, 'subjects_str': 'BIO/BSC',       'min_grade': 'C'},
            {'slot': 4, 'subjects_str': 'PHY/PSC/MAT A', 'min_grade': 'C'},
        ],
    },
    'K13': {
        'name': 'Diploma in Physiotherapy',
        'mean_grade': 'C',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',           'min_grade': 'C'},
            {'slot': 2, 'subjects_str': 'BIO',               'min_grade': 'C-'},
            {'slot': 3, 'subjects_str': 'CHE/MAT A/PHY/PSC', 'min_grade': 'C-'},
            {'slot': 4, 'subjects_str': 'CHE/MAT A/PHY/PSC', 'min_grade': 'C-'},
        ],
    },
    'K14': {
        'name': 'Diploma in Medical Engineering',
        'mean_grade': 'C',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',                 'min_grade': 'C'},
            {'slot': 2, 'subjects_str': 'MAT A',                   'min_grade': 'C-'},
            {'slot': 3, 'subjects_str': 'PHY/PSC',                 'min_grade': 'C-'},
            {'slot': 4, 'subjects_str': 'BIO/BSC/CHE/ECT/MW/DRD', 'min_grade': 'D+'},
        ],
    },
    'K15': {
        'name': 'Diploma in Public Health',
        'mean_grade': 'C',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',       'min_grade': 'C'},
            {'slot': 2, 'subjects_str': 'BIO/BSC',       'min_grade': 'C'},
            {'slot': 3, 'subjects_str': 'MAT A',         'min_grade': 'C-'},
            {'slot': 4, 'subjects_str': 'PHY/PSC/CHE',   'min_grade': 'C-'},
        ],
    },
    'K16': {
        'name': 'Diploma in Dental Technology',
        'mean_grade': 'C',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',                'min_grade': 'C'},
            {'slot': 2, 'subjects_str': 'PHY/PSC/CHE',            'min_grade': 'C'},
            {'slot': 3, 'subjects_str': 'BIO/BSC',                'min_grade': 'C-'},
            {'slot': 4, 'subjects_str': 'MW/PHY/PSC/CHE/MAT A',   'min_grade': 'C-'},
        ],
    },
    'K17': {
        'name': 'Diploma in Orthopedic and Trauma Medicine',
        'mean_grade': 'C',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',           'min_grade': 'C'},
            {'slot': 2, 'subjects_str': 'BIO/BSC',           'min_grade': 'C'},
            {'slot': 3, 'subjects_str': 'PHY/PSC/CHE/MAT A', 'min_grade': 'C-'},
        ],
    },
    'K18': {
        'name': 'Diploma in Medical Social Work',
        'mean_grade': 'C',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',                                  'min_grade': 'C'},
            {'slot': 2, 'subjects_str': 'BIO/BSC',                                  'min_grade': 'D+'},
            {'slot': 3, 'subjects_str': 'CHE/PHY/PSC/MAT A/HSC/AGR/BST/GEO/HAG/CRE/IRE', 'min_grade': 'C-'},
        ],
    },
    'K19': {
        'name': 'Diploma in Health Counselling',
        'mean_grade': 'C',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',         'min_grade': 'C'},
            {'slot': 2, 'subjects_str': 'BIO/BSC',         'min_grade': 'D+'},
            {'slot': 3, 'subjects_str': 'HAG/CRE/IRE/HRE', 'min_grade': 'C-'},
        ],
    },
    'K20': {
        'name': 'Diploma in Community Health',
        'mean_grade': 'C',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',                      'min_grade': 'C-'},
            {'slot': 2, 'subjects_str': 'BIO/BSC',                      'min_grade': 'D+'},
            {'slot': 3, 'subjects_str': 'MAT A/CHE/HSC/AGR/PHY/PSC',   'min_grade': 'D'},
        ],
    },
    'K21': {
        'name': 'Diploma in Emergency Medical Technology',
        'mean_grade': 'C',
        'requirements': [],
    },
    'K22': {
        'name': 'Certificate in Health Records and Information Technology',
        'mean_grade': 'C-',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',                                        'min_grade': 'C-'},
            {'slot': 2, 'subjects_str': 'BIO/BSC',                                        'min_grade': 'D'},
            {'slot': 3, 'subjects_str': 'MAT A',                                          'min_grade': 'D-'},
            {'slot': 4, 'subjects_str': 'PHY/PSC/CHE/GSC/CMP/COM/AGR/HSC/ECON/GEO/BST', 'min_grade': 'D+'},
        ],
    },
    'K23': {
        'name': 'Certificate in Kenya Enrolled Community Health Nursing',
        'mean_grade': 'C-',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',           'min_grade': 'C-'},
            {'slot': 2, 'subjects_str': 'BIO/BSC',           'min_grade': 'C-'},
            {'slot': 3, 'subjects_str': 'CHE/PHY/PSC/MAT A', 'min_grade': 'D+'},
        ],
    },
    'K24': {
        'name': 'Certificate in Nutrition and Dietetics',
        'mean_grade': 'D+',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',                  'min_grade': 'D+'},
            {'slot': 2, 'subjects_str': 'BIO/BSC',                  'min_grade': 'D'},
            {'slot': 3, 'subjects_str': 'CHE/PSC',                  'min_grade': 'D'},
            {'slot': 4, 'subjects_str': 'MAT A/HSC/AGR/PHY/GSC',   'min_grade': 'D'},
        ],
    },
    'K25': {
        'name': 'Certificate in Medical Engineering',
        'mean_grade': 'C-',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',                 'min_grade': 'C-'},
            {'slot': 2, 'subjects_str': 'MAT A',                   'min_grade': 'D'},
            {'slot': 3, 'subjects_str': 'PHY/PSC',                 'min_grade': 'D-'},
            {'slot': 4, 'subjects_str': 'CHE/BIO/BSC/ECT/MW/DRD', 'min_grade': 'D'},
        ],
    },
    'K26': {
        'name': 'Certificate in Orthopedic Trauma Medicine',
        'mean_grade': 'C-',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',                               'min_grade': 'C-'},
            {'slot': 2, 'subjects_str': 'BIO/BSC',                               'min_grade': 'C-'},
            {'slot': 3, 'subjects_str': 'PHY/PSC/MAT A/CHE/MW/DRD/HSC/AGR/WW/CMP', 'min_grade': 'D+'},
        ],
    },
    'K27': {
        'name': 'Certificate in Public Health',
        'mean_grade': 'C-',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS', 'min_grade': 'C-'},
            {'slot': 2, 'subjects_str': 'BIO/BSC', 'min_grade': 'C-'},
            {'slot': 3, 'subjects_str': 'MAT A',   'min_grade': 'D'},
        ],
    },
    'K28': {
        'name': 'Certificate in Community Health Assistant',
        'mean_grade': 'C-',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',                    'min_grade': 'D+'},
            {'slot': 2, 'subjects_str': 'BIO/BSC',                    'min_grade': 'D'},
            {'slot': 3, 'subjects_str': 'MAT A/CHE/PHY/PSC/AGR/HSC', 'min_grade': 'D'},
        ],
    },
    'K29': {
        'name': 'Certificate in Medical Emergency Technician',
        'mean_grade': 'C-',
        'requirements': [],
    },
    'K30': {
        'name': 'Diploma in Speech and Language Therapy',
        'mean_grade': 'C',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',        'min_grade': 'C-'},
            {'slot': 2, 'subjects_str': 'BIO/BSC',        'min_grade': 'C-'},
            {'slot': 3, 'subjects_str': 'PHY/CHE/MAT A',  'min_grade': 'C-'},
        ],
    },
    'K31': {
        'name': 'Diploma in Kenya Registered Nursing',
        'mean_grade': 'C',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',           'min_grade': 'C'},
            {'slot': 2, 'subjects_str': 'BIO/BSC',           'min_grade': 'C'},
            {'slot': 3, 'subjects_str': 'PHY/PSC/CHE/MAT A', 'min_grade': 'C-'},
        ],
    },
    'K32': {
        'name': 'Diploma in Clinical Medicine and Surgery',
        'mean_grade': 'C',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',       'min_grade': 'C'},
            {'slot': 2, 'subjects_str': 'BIO/BSC',       'min_grade': 'C'},
            {'slot': 3, 'subjects_str': 'CHE/PSC',       'min_grade': 'C-'},
            {'slot': 4, 'subjects_str': 'PHY/PSC/MAT A', 'min_grade': 'C-'},
        ],
    },
    'K33': {
        'name': 'Diploma in Mortuary Science',
        'mean_grade': 'C-',
        'requirements': [],
    },
    'K34': {
        'name': 'Diploma in Health Promotion',
        'mean_grade': 'C',
        'requirements': [
            {'slot': 1, 'subjects_str': 'ENG/KIS',           'min_grade': 'C'},
            {'slot': 2, 'subjects_str': 'BIO/BSC',           'min_grade': 'C-'},
            {'slot': 3, 'subjects_str': 'PHY/PSC/CHE/MAT A', 'min_grade': 'D+'},
        ],
    },
}


# ─────────────────────────────────────────────────────────────
# 2.  ALL 342 OFFERINGS  (programme_code, campus_name, k_suffix)
# ─────────────────────────────────────────────────────────────
OFFERINGS = [
    # K01
    ('5000K01', 'KMTC Nairobi', 'K01'),
    # K02
    ('4780K02', 'KMTC Homa Bay', 'K02'),
    ('4830K02', 'KMTC Karen - Nairobi', 'K02'),
    ('4890K02', 'KMTC Lodwar', 'K02'),
    ('4915K02', 'KMTC Makueni', 'K02'),
    ('4970K02', 'KMTC Molo', 'K02'),
    ('5030K02', 'KMTC Nyandarua', 'K02'),
    ('5100K02', 'KMTC Thika', 'K02'),
    # K03
    ('4725K03', 'KMTC Bondo', 'K03'),
    ('4790K03', 'KMTC Isiolo', 'K03'),
    ('5000K03', 'KMTC Nairobi', 'K03'),
    ('5005K03', 'KMTC Nakuru', 'K03'),
    ('5070K03', 'KMTC Siaya', 'K03'),
    # K04
    ('4725K04', 'KMTC Bondo', 'K04'),
    ('4735K04', 'KMTC Busia', 'K04'),
    ('4755K04', 'KMTC Eldoret', 'K04'),
    ('4765K04', 'KMTC Garissa', 'K04'),
    ('4780K04', 'KMTC Homa Bay', 'K04'),
    ('4795K04', 'KMTC Iten', 'K04'),
    ('4800K04', 'KMTC Kabarnet', 'K04'),
    ('4820K04', 'KMTC Kapkatet', 'K04'),
    ('4825K04', 'KMTC Kaptumo', 'K04'),
    ('4855K04', 'KMTC Kitale', 'K04'),
    ('4860K04', 'KMTC Kitui', 'K04'),
    ('4890K04', 'KMTC Lodwar', 'K04'),
    ('4905K04', 'KMTC Machakos', 'K04'),
    ('4955K04', 'KMTC Meru - Miathene Satellite', 'K04'),
    ('4960K04', 'KMTC Migori', 'K04'),
    ('4980K04', 'KMTC Mosoriot', 'K04'),
    ('4985K04', 'KMTC Msambweni', 'K04'),
    ('4995K04', 'KMTC Mwingi', 'K04'),
    ('5000K04', 'KMTC Nairobi', 'K04'),
    ('5005K04', 'KMTC Nakuru', 'K04'),
    ('5015K04', 'KMTC Nyahururu', 'K04'),
    ('5025K04', 'KMTC Nyamira', 'K04'),
    ('5030K04', 'KMTC Nyandarua', 'K04'),
    ('5040K04', 'KMTC Nyeri', 'K04'),
    ('5050K04', 'KMTC Port Reitz', 'K04'),
    ('5070K04', 'KMTC Siaya', 'K04'),
    ('5080K04', 'KMTC Sigowet', 'K04'),
    ('5100K04', 'KMTC Thika', 'K04'),
    ('5120K04', 'KMTC Voi', 'K04'),
    ('5130K04', 'KMTC Webuye', 'K04'),
    # K06
    ('4780K06', 'KMTC Homa Bay', 'K06'),
    ('4805K06', 'KMTC Kakamega', 'K06'),
    ('4865K06', 'KMTC Kombewa', 'K06'),
    ('4980K06', 'KMTC Mosoriot', 'K06'),
    # K07
    ('4755K07', 'KMTC Eldoret', 'K07'),
    ('4820K07', 'KMTC Kapkatet', 'K07'),
    ('4850K07', 'KMTC Kisumu', 'K07'),
    ('4930K07', 'KMTC Manza', 'K07'),
    ('4975K07', 'KMTC Mombasa', 'K07'),
    ('5000K07', 'KMTC Nairobi', 'K07'),
    ('5005K07', 'KMTC Nakuru', 'K07'),
    ('5040K07', 'KMTC Nyeri', 'K07'),
    ('5070K07', 'KMTC Siaya', 'K07'),
    # K08
    ('4760K08', 'KMTC Embu', 'K08'),
    ('4805K08', 'KMTC Kakamega', 'K08'),
    ('4845K08', 'KMTC Kisii', 'K08'),
    ('4860K08', 'KMTC Kitui', 'K08'),
    ('4865K08', 'KMTC Kombewa', 'K08'),
    ('4880K08', 'KMTC Lake Victoria', 'K08'),
    ('4905K08', 'KMTC Machakos', 'K08'),
    ('4945K08', 'KMTC Meru', 'K08'),
    ('5000K08', 'KMTC Nairobi', 'K08'),
    ('5005K08', 'KMTC Nakuru', 'K08'),
    ('5040K08', 'KMTC Nyeri', 'K08'),
    ('5050K08', 'KMTC Port Reitz', 'K08'),
    # K09
    ('4905K09', 'KMTC Machakos', 'K09'),
    ('4910K09', 'KMTC Makindu', 'K09'),
    ('4975K09', 'KMTC Mombasa', 'K09'),
    ('5000K09', 'KMTC Nairobi', 'K09'),
    ('5075K09', 'KMTC Siaya - Ugunja Satellite', 'K09'),
    # K10
    ('5000K10', 'KMTC Nairobi', 'K10'),
    # K11
    ('5000K11', 'KMTC Nairobi', 'K11'),
    ('5050K11', 'KMTC Port Reitz', 'K11'),
    # K12
    ('4850K12', 'KMTC Kisumu', 'K12'),
    ('4930K12', 'KMTC Manza', 'K12'),
    ('4975K12', 'KMTC Mombasa', 'K12'),
    ('5000K12', 'KMTC Nairobi', 'K12'),
    ('5005K12', 'KMTC Nakuru', 'K12'),
    ('5040K12', 'KMTC Nyeri', 'K12'),
    # K13
    ('4770K13', 'KMTC Gatundu', 'K13'),
    ('4780K13', 'KMTC Homa Bay', 'K13'),
    ('5000K13', 'KMTC Nairobi', 'K13'),
    ('5005K13', 'KMTC Nakuru', 'K13'),
    ('5050K13', 'KMTC Port Reitz', 'K13'),
    # K14
    ('4755K14', 'KMTC Eldoret', 'K14'),
    ('4945K14', 'KMTC Meru', 'K14'),
    ('5000K14', 'KMTC Nairobi', 'K14'),
    # K15
    ('4760K15', 'KMTC Embu', 'K15'),
    ('4805K15', 'KMTC Kakamega', 'K15'),
    ('4835K15', 'KMTC Karuri', 'K15'),
    ('4850K15', 'KMTC Kisumu', 'K15'),
    ('4860K15', 'KMTC Kitui', 'K15'),
    ('4875K15', 'KMTC Kwale', 'K15'),
    ('4880K15', 'KMTC Lake Victoria', 'K15'),
    ('5000K15', 'KMTC Nairobi', 'K15'),
    ('5040K15', 'KMTC Nyeri', 'K15'),
    # K16
    ('5000K16', 'KMTC Nairobi', 'K16'),
    ('5005K16', 'KMTC Nakuru', 'K16'),
    # K17
    ('4845K17', 'KMTC Kisii', 'K17'),
    ('4905K17', 'KMTC Machakos', 'K17'),
    ('5000K17', 'KMTC Nairobi', 'K17'),
    ('5040K17', 'KMTC Nyeri', 'K17'),
    # K18
    ('4785K18', 'KMTC Imenti', 'K18'),
    ('4820K18', 'KMTC Kapkatet', 'K18'),
    ('4835K18', 'KMTC Karuri', 'K18'),
    # K19
    ('4760K19', 'KMTC Embu', 'K19'),
    ('4915K19', 'KMTC Makueni', 'K19'),
    ('4935K19', 'KMTC Mathare', 'K19'),
    # K20
    ('4775K20', 'KMTC Gatundu - Mutunguru Satellite', 'K20'),
    ('4785K20', 'KMTC Imenti', 'K20'),
    ('4790K20', 'KMTC Isiolo', 'K20'),
    ('4795K20', 'KMTC Iten', 'K20'),
    ('4860K20', 'KMTC Kitui', 'K20'),
    ('4910K20', 'KMTC Makindu', 'K20'),
    ('4980K20', 'KMTC Mosoriot', 'K20'),
    ('5000K20', 'KMTC Nairobi', 'K20'),
    ('5005K20', 'KMTC Nakuru', 'K20'),
    ('5015K20', 'KMTC Nyahururu', 'K20'),
    ('5020K20', 'KMTC Nyamache', 'K20'),
    ('5055K20', 'KMTC Rachuonyo', 'K20'),
    ('5080K20', 'KMTC Sigowet', 'K20'),
    ('5090K20', 'KMTC Taveta', 'K20'),
    ('5130K20', 'KMTC Webuye', 'K20'),
    ('5175K20', 'KMTC Kakamega - Navakholo', 'K20'),
    ('5180K20', 'KMTC Kitui - Mutomo', 'K20'),
    # K21
    ('5000K21', 'KMTC Nairobi', 'K21'),
    # K22
    ('4725K22', 'KMTC Bondo', 'K22'),
    ('4750K22', 'KMTC Chwele', 'K22'),
    ('4785K22', 'KMTC Imenti', 'K22'),
    ('4790K22', 'KMTC Isiolo', 'K22'),
    ('4815K22', 'KMTC Kapenguria', 'K22'),
    ('4820K22', 'KMTC Kapkatet', 'K22'),
    ('4825K22', 'KMTC Kaptumo', 'K22'),
    ('4860K22', 'KMTC Kitui', 'K22'),
    ('4870K22', 'KMTC Kuria', 'K22'),
    ('4885K22', 'KMTC Lamu', 'K22'),
    ('4900K22', 'KMTC Lugari', 'K22'),
    ('4920K22', 'KMTC Makueni - Mbuvo Satellite', 'K22'),
    ('4930K22', 'KMTC Manza', 'K22'),
    ('4950K22', 'KMTC Meru - Maua Satellite', 'K22'),
    ('4970K22', 'KMTC Molo', 'K22'),
    ('4975K22', 'KMTC Mombasa', 'K22'),
    ('4985K22', 'KMTC Msambweni', 'K22'),
    ('4990K22', 'KMTC Muranga', 'K22'),
    ('5000K22', 'KMTC Nairobi', 'K22'),
    ('5010K22', 'KMTC Ndhiwa', 'K22'),
    ('5020K22', 'KMTC Nyamache', 'K22'),
    ('5045K22', 'KMTC Othaya', 'K22'),
    ('5055K22', 'KMTC Rachuonyo', 'K22'),
    ('5060K22', 'KMTC Rera', 'K22'),
    ('5070K22', 'KMTC Siaya', 'K22'),
    ('5085K22', 'KMTC Tana River', 'K22'),
    ('5095K22', 'KMTC Teso', 'K22'),
    ('5110K22', 'KMTC Ugenya', 'K22'),
    ('5120K22', 'KMTC Voi', 'K22'),
    ('5130K22', 'KMTC Webuye', 'K22'),
    ('5215K22', 'KMTC Narok', 'K22'),
    ('5220K22', 'KMTC Muranga - Kangema Satellite', 'K22'),
    # K23
    ('4720K23', 'KMTC Bomet', 'K23'),
    ('4765K23', 'KMTC Garissa', 'K23'),
    ('4790K23', 'KMTC Isiolo', 'K23'),
    ('4800K23', 'KMTC Kabarnet', 'K23'),
    ('4815K23', 'KMTC Kapenguria', 'K23'),
    ('4840K23', 'KMTC Kilifi', 'K23'),
    ('4860K23', 'KMTC Kitui', 'K23'),
    ('4890K23', 'KMTC Lodwar', 'K23'),
    ('4895K23', 'KMTC Loitokitok', 'K23'),
    ('4985K23', 'KMTC Msambweni', 'K23'),
    ('5125K23', 'KMTC Wajir', 'K23'),
    # K24
    ('4750K24', 'KMTC Chwele', 'K24'),
    ('4780K24', 'KMTC Homa Bay', 'K24'),
    ('4800K24', 'KMTC Kabarnet', 'K24'),
    ('4815K24', 'KMTC Kapenguria', 'K24'),
    ('4830K24', 'KMTC Karen - Nairobi', 'K24'),
    ('4875K24', 'KMTC Kwale', 'K24'),
    ('4890K24', 'KMTC Lodwar', 'K24'),
    ('4920K24', 'KMTC Makueni - Mbuvo Satellite', 'K24'),
    ('4970K24', 'KMTC Molo', 'K24'),
    ('5030K24', 'KMTC Nyandarua', 'K24'),
    ('5060K24', 'KMTC Rera', 'K24'),
    ('5100K24', 'KMTC Thika', 'K24'),
    # K25
    ('4720K25', 'KMTC Bomet', 'K25'),
    ('4755K25', 'KMTC Eldoret', 'K25'),
    ('4760K25', 'KMTC Embu', 'K25'),
    ('4840K25', 'KMTC Kilifi', 'K25'),
    ('4845K25', 'KMTC Kisii', 'K25'),
    ('4850K25', 'KMTC Kisumu', 'K25'),
    ('4880K25', 'KMTC Lake Victoria', 'K25'),
    ('4895K25', 'KMTC Loitokitok', 'K25'),
    ('4910K25', 'KMTC Makindu', 'K25'),
    ('4945K25', 'KMTC Meru', 'K25'),
    ('5000K25', 'KMTC Nairobi', 'K25'),
    # K26
    ('4730K26', 'KMTC Bungoma', 'K26'),
    ('4735K26', 'KMTC Busia', 'K26'),
    ('4745K26', 'KMTC Chuka', 'K26'),
    ('4765K26', 'KMTC Garissa', 'K26'),
    ('4805K26', 'KMTC Kakamega', 'K26'),
    ('4810K26', 'KMTC Kangundo', 'K26'),
    ('4825K26', 'KMTC Kaptumo', 'K26'),
    ('4845K26', 'KMTC Kisii', 'K26'),
    ('4905K26', 'KMTC Machakos', 'K26'),
    ('4910K26', 'KMTC Makindu', 'K26'),
    ('4915K26', 'KMTC Makueni', 'K26'),
    ('4920K26', 'KMTC Makueni - Mbuvo Satellite', 'K26'),
    ('4940K26', 'KMTC Mbooni', 'K26'),
    ('4955K26', 'KMTC Meru - Miathene Satellite', 'K26'),
    ('5005K26', 'KMTC Nakuru', 'K26'),
    ('5050K26', 'KMTC Port Reitz', 'K26'),
    ('5065K26', 'KMTC Shianda - Mumias', 'K26'),
    ('5070K26', 'KMTC Siaya', 'K26'),
    ('5080K26', 'KMTC Sigowet', 'K26'),
    ('5100K26', 'KMTC Thika', 'K26'),
    ('5115K26', 'KMTC Vihiga', 'K26'),
    ('5120K26', 'KMTC Voi', 'K26'),
    # K27
    ('4760K27', 'KMTC Embu', 'K27'),
    ('4800K27', 'KMTC Kabarnet', 'K27'),
    ('4805K27', 'KMTC Kakamega', 'K27'),
    ('4835K27', 'KMTC Karuri', 'K27'),
    ('4860K27', 'KMTC Kitui', 'K27'),
    ('4870K27', 'KMTC Kuria', 'K27'),
    ('4875K27', 'KMTC Kwale', 'K27'),
    ('4880K27', 'KMTC Lake Victoria', 'K27'),
    ('4900K27', 'KMTC Lugari', 'K27'),
    ('4930K27', 'KMTC Manza', 'K27'),
    ('5005K27', 'KMTC Nakuru', 'K27'),
    ('5040K27', 'KMTC Nyeri', 'K27'),
    ('5045K27', 'KMTC Othaya', 'K27'),
    ('5090K27', 'KMTC Taveta', 'K27'),
    ('5105K27', 'KMTC Trans Mara', 'K27'),
    # K28
    ('4720K28', 'KMTC Bomet', 'K28'),
    ('4740K28', 'KMTC Chemolingot', 'K28'),
    ('4750K28', 'KMTC Chwele', 'K28'),
    ('4760K28', 'KMTC Embu', 'K28'),
    ('4765K28', 'KMTC Garissa', 'K28'),
    ('4785K28', 'KMTC Imenti', 'K28'),
    ('4790K28', 'KMTC Isiolo', 'K28'),
    ('4795K28', 'KMTC Iten', 'K28'),
    ('4800K28', 'KMTC Kabarnet', 'K28'),
    ('4805K28', 'KMTC Kakamega', 'K28'),
    ('4810K28', 'KMTC Kangundo', 'K28'),
    ('4815K28', 'KMTC Kapenguria', 'K28'),
    ('4870K28', 'KMTC Kuria', 'K28'),
    ('4875K28', 'KMTC Kwale', 'K28'),
    ('4890K28', 'KMTC Lodwar', 'K28'),
    ('4900K28', 'KMTC Lugari', 'K28'),
    ('4910K28', 'KMTC Makindu', 'K28'),
    ('4920K28', 'KMTC Makueni - Mbuvo Satellite', 'K28'),
    ('4925K28', 'KMTC Mandera', 'K28'),
    ('4930K28', 'KMTC Manza', 'K28'),
    ('4940K28', 'KMTC Mbooni', 'K28'),
    ('4950K28', 'KMTC Meru - Maua Satellite', 'K28'),
    ('4965K28', 'KMTC Migori - Awendo Satellite', 'K28'),
    ('4980K28', 'KMTC Mosoriot', 'K28'),
    ('5000K28', 'KMTC Nairobi', 'K28'),
    ('5010K28', 'KMTC Ndhiwa', 'K28'),
    ('5015K28', 'KMTC Nyahururu', 'K28'),
    ('5020K28', 'KMTC Nyamache', 'K28'),
    ('5035K28', 'KMTC Nyandarua - Kinangop Satellite', 'K28'),
    ('5045K28', 'KMTC Othaya', 'K28'),
    ('5055K28', 'KMTC Rachuonyo', 'K28'),
    ('5060K28', 'KMTC Rera', 'K28'),
    ('5065K28', 'KMTC Shianda - Mumias', 'K28'),
    ('5075K28', 'KMTC Siaya - Ugunja Satellite', 'K28'),
    ('5080K28', 'KMTC Sigowet', 'K28'),
    ('5085K28', 'KMTC Tana River', 'K28'),
    ('5090K28', 'KMTC Taveta', 'K28'),
    ('5095K28', 'KMTC Teso', 'K28'),
    ('5105K28', 'KMTC Trans Mara', 'K28'),
    ('5110K28', 'KMTC Ugenya', 'K28'),
    ('5115K28', 'KMTC Vihiga', 'K28'),
    ('5120K28', 'KMTC Voi', 'K28'),
    ('5130K28', 'KMTC Webuye', 'K28'),
    ('5175K28', 'KMTC Kakamega - Navakholo', 'K28'),
    ('5180K28', 'KMTC Kitui - Mutomo', 'K28'),
    ('5220K28', 'KMTC Muranga - Kangema Satellite', 'K28'),
    # K29
    ('4755K29', 'KMTC Eldoret', 'K29'),
    ('4760K29', 'KMTC Embu', 'K29'),
    ('4765K29', 'KMTC Garissa', 'K29'),
    ('4770K29', 'KMTC Gatundu', 'K29'),
    ('4805K29', 'KMTC Kakamega', 'K29'),
    ('4850K29', 'KMTC Kisumu', 'K29'),
    ('4910K29', 'KMTC Makindu', 'K29'),
    ('4935K29', 'KMTC Mathare', 'K29'),
    ('4975K29', 'KMTC Mombasa', 'K29'),
    ('5000K29', 'KMTC Nairobi', 'K29'),
    ('5040K29', 'KMTC Nyeri', 'K29'),
    ('5050K29', 'KMTC Port Reitz', 'K29'),
    ('5090K29', 'KMTC Taveta', 'K29'),
    ('5100K29', 'KMTC Thika', 'K29'),
    ('5120K29', 'KMTC Voi', 'K29'),
    # K30
    ('5000K30', 'KMTC Nairobi', 'K30'),
    # K31
    ('4770K31', 'KMTC Gatundu', 'K31'),
    # K32
    ('4720K32', 'KMTC Bomet', 'K32'),
    ('4725K32', 'KMTC Bondo', 'K32'),
    ('4730K32', 'KMTC Bungoma', 'K32'),
    ('4735K32', 'KMTC Busia', 'K32'),
    ('4745K32', 'KMTC Chuka', 'K32'),
    ('4755K32', 'KMTC Eldoret', 'K32'),
    ('4760K32', 'KMTC Embu', 'K32'),
    ('4765K32', 'KMTC Garissa', 'K32'),
    ('4770K32', 'KMTC Gatundu', 'K32'),
    ('4780K32', 'KMTC Homa Bay', 'K32'),
    ('4790K32', 'KMTC Isiolo', 'K32'),
    ('4795K32', 'KMTC Iten', 'K32'),
    ('4800K32', 'KMTC Kabarnet', 'K32'),
    ('4805K32', 'KMTC Kakamega', 'K32'),
    ('4815K32', 'KMTC Kapenguria', 'K32'),
    ('4820K32', 'KMTC Kapkatet', 'K32'),
    ('4840K32', 'KMTC Kilifi', 'K32'),
    ('4845K32', 'KMTC Kisii', 'K32'),
    ('4850K32', 'KMTC Kisumu', 'K32'),
    ('4855K32', 'KMTC Kitale', 'K32'),
    ('4860K32', 'KMTC Kitui', 'K32'),
    ('4895K32', 'KMTC Loitokitok', 'K32'),
    ('4905K32', 'KMTC Machakos', 'K32'),
    ('4910K32', 'KMTC Makindu', 'K32'),
    ('4915K32', 'KMTC Makueni', 'K32'),
    ('4945K32', 'KMTC Meru', 'K32'),
    ('4955K32', 'KMTC Meru - Miathene Satellite', 'K32'),
    ('4975K32', 'KMTC Mombasa', 'K32'),
    ('4980K32', 'KMTC Mosoriot', 'K32'),
    ('4985K32', 'KMTC Msambweni', 'K32'),
    ('4990K32', 'KMTC Muranga', 'K32'),
    ('4995K32', 'KMTC Mwingi', 'K32'),
    ('5000K32', 'KMTC Nairobi', 'K32'),
    ('5005K32', 'KMTC Nakuru', 'K32'),
    ('5015K32', 'KMTC Nyahururu', 'K32'),
    ('5025K32', 'KMTC Nyamira', 'K32'),
    ('5030K32', 'KMTC Nyandarua', 'K32'),
    ('5040K32', 'KMTC Nyeri', 'K32'),
    ('5050K32', 'KMTC Port Reitz', 'K32'),
    ('5070K32', 'KMTC Siaya', 'K32'),
    ('5100K32', 'KMTC Thika', 'K32'),
    ('5120K32', 'KMTC Voi', 'K32'),
    ('5130K32', 'KMTC Webuye', 'K32'),
    # K33
    ('4850K33', 'KMTC Kisumu', 'K33'),
    ('4975K33', 'KMTC Mombasa', 'K33'),
    ('5000K33', 'KMTC Nairobi', 'K33'),
    # K34
    ('5000K34', 'KMTC Nairobi', 'K34'),
]


class Command(BaseCommand):
    help = 'Seed all KMTC campuses, programmes, and offerings from the KUCCPS portal data.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Delete existing KMTC institutions and courses before seeding.'
        )

    def handle(self, *args, **options):
        self.stdout.write('-' * 60)
        self.stdout.write('seed_kmtc — starting')
        self.stdout.write('-' * 60)

        with transaction.atomic():
            if options['clear']:
                self._clear_existing()
            inst_type = self._ensure_institution_type()
            course_type = self._ensure_course_type()
            campus_map = self._seed_campuses(inst_type)
            course_map = self._seed_courses(course_type)
            self._seed_offerings(campus_map, course_map)

        self.stdout.write(self.style.SUCCESS('\nDone.'))

    # ─────────────────────────────────────────────────
    def _clear_existing(self):
        self.stdout.write('\n[0] Clearing existing KMTC data...')
        inst_type = InstitutionType.objects.filter(name='KMTC').first()
        if inst_type:
            n, _ = Institution.objects.filter(institution_type=inst_type).delete()
            self.stdout.write(f'  Deleted {n} KMTC institutions')
        ct = CourseType.objects.filter(name='KMTC').first()
        if ct:
            n, _ = Course.objects.filter(course_type=ct).delete()
            self.stdout.write(f'  Deleted {n} KMTC courses')

    def _ensure_institution_type(self):
        inst_type, created = InstitutionType.objects.get_or_create(
            name='KMTC',
            defaults={
                'description': 'Kenya Medical Training College campuses',
                'icon': 'bi-hospital-fill',
                'color_code': '#dc2626',
            }
        )
        action = 'Created' if created else 'Found'
        self.stdout.write(f'\n[1] Institution type: {action} "{inst_type.name}"')
        return inst_type

    def _ensure_course_type(self):
        ct, created = CourseType.objects.get_or_create(
            name='KMTC',
            defaults={
                'description': 'Kenya Medical Training College programmes',
                'icon': 'bi-hospital-fill',
                'color_code': '#dc2626',
            }
        )
        action = 'Created' if created else 'Found'
        self.stdout.write(f'[2] Course type: {action} "{ct.name}"')
        return ct

    def _seed_campuses(self, inst_type):
        self.stdout.write('\n[3] Campuses')
        # Collect unique campus names from OFFERINGS
        campus_names = sorted({campus_name for _, campus_name, _ in OFFERINGS})
        campus_map = {}
        created_count = updated_count = 0

        for name in campus_names:
            # Derive location from name (strip "KMTC " prefix)
            location = name.replace('KMTC ', '').title()
            inst, created = Institution.objects.get_or_create(
                name=name,
                institution_type=inst_type,
                defaults={'location': location, 'description': f'KMTC campus — {location}'}
            )
            campus_map[name] = inst
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(f'  {created_count} created, {updated_count} already existed ({len(campus_map)} total)')
        return campus_map

    def _seed_courses(self, course_type):
        self.stdout.write('\n[4] Programmes (courses)')
        course_map = {}
        created_count = updated_count = 0

        for k_code, prog in PROGRAMMES.items():
            course, created = Course.objects.get_or_create(
                name=prog['name'],
                course_type=course_type,
                defaults={
                    'minimum_mean_grade': prog['mean_grade'],
                    'subject_requirements': prog['requirements'],
                    'description': f"KMTC programme. Minimum mean grade: {prog['mean_grade']}.",
                }
            )
            if not created:
                # Update requirements in case they changed
                course.minimum_mean_grade = prog['mean_grade']
                course.subject_requirements = prog['requirements']
                course.save(update_fields=['minimum_mean_grade', 'subject_requirements'])
                updated_count += 1
            else:
                created_count += 1

            course_map[k_code] = course

        self.stdout.write(f'  {created_count} created, {updated_count} updated ({len(course_map)} total)')
        return course_map

    def _seed_offerings(self, campus_map, course_map):
        self.stdout.write('\n[5] Offerings (campus × programme links)')
        created_count = skipped_count = 0

        for programme_code, campus_name, k_code in OFFERINGS:
            institution = campus_map.get(campus_name)
            course = course_map.get(k_code)
            if not institution or not course:
                self.stdout.write(self.style.WARNING(
                    f'  SKIP {programme_code}: campus={campus_name}, k={k_code}'
                ))
                skipped_count += 1
                continue

            _, created = CourseOffering.objects.update_or_create(
                course=course,
                institution=institution,
                defaults={'programme_code': programme_code}
            )
            if created:
                created_count += 1

        total = created_count + (len(OFFERINGS) - skipped_count - created_count)
        self.stdout.write(
            f'  {created_count} new offerings, {len(OFFERINGS) - skipped_count - created_count} already existed, '
            f'{skipped_count} skipped'
        )
        self.stdout.write(f'  Total offerings processed: {len(OFFERINGS) - skipped_count}')
