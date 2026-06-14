"""
Management command: seed_tvet

Populates:
  - InstitutionType  : "Public TVET" and "Private TVET"
  - Institution      : 220 TVET institutions with location & abbreviation
  - CourseType       : "TVET"
  - CourseCategory   : one per TVET level (Diploma/L6, Certificate/L5, Artisan/L4, Craft/L3, Short Course, Trade Test, Proficiency, Professional)
  - Course           : 118 canonical diploma programmes with trade category & subject requirements
  - CourseOffering   : 3 273 institution × programme links (from DIPLOMA_PROGRAMMES.pdf / KUCCPS)

Source data: DIPLOMA_PROGRAMMES.pdf (KUCCPS portal), TVET_CLUSTER_DOCUMENT_2025.pdf
Excluded: teacher-training programmes, expired / revoked institutions.

Usage:
    py manage.py seed_tvet
    py manage.py seed_tvet --clear     # wipe all TVET data first
"""

import json, os
from django.core.management.base import BaseCommand
from django.db import transaction

from institutions.models import Institution, InstitutionType
from courses.models import Course, CourseType, CourseCategory, CourseOffering


# ─────────────────────────────────────────────────────────────────────────────
# 1.  INSTITUTIONS  (name, location, abbreviation, is_public)
# ─────────────────────────────────────────────────────────────────────────────
INSTITUTIONS = [
    ('Ahmed Shahame Mwidani Technical Training Institute', 'Mombasa', 'ASMTTI', True),
    ('Aldai Technical Training Institute', 'Aldai, Nandi', 'ATTI', True),
    ('Alupe University Tvet Institute', 'Busia', 'AUTI', True),
    ('Bandari Maritime Academy', 'Mombasa', 'BMA', True),
    ('Baringo Technical College', 'Baringo', 'BTC', True),
    ('Belgut Technical And Vocational College', 'Belgut, Kericho', 'BTVC', True),
    ('Bomet Technical & Vocational College', 'Bomet', 'BMTVC', True),
    ('Bondo Technical Training Institute', 'Bondo, Siaya', 'BTTI', True),
    ('Borabu Technical And Vocational College', 'Borabu, Nyamira', 'BRTVC', True),
    ('Bukura Agricultural College', 'Kakamega', 'BAC', True),
    ('Bungoma North Technical And Vocational College', 'Bungoma North', 'BNTVC', True),
    ('Bunyala Technical And Vocational College', 'Bunyala, Busia', 'BUTVC', True),
    ('Bureti Technical Training Institute', 'Bureti, Kericho', 'BRTTI', True),
    ('Bushiangala Technical Training Institute', 'Bushiangala, Kakamega', 'BSTTI', True),
    ('Butere Technical And Vocational College', 'Butere, Kakamega', 'BETVC', True),
    ('Butula Technical & Vocational College', 'Butula, Busia', 'BLTVC', True),
    ('Centre For Tourism Training And Research', 'Nairobi', 'CTTR', True),
    ('Chamasiri Technical And Vocational College', 'Chamasiri, Kisii', 'CHATVC', True),
    ('Chanzeywe Technical And Vocational College', 'Chanzeywe, Kilifi', 'CZTVC', True),
    ('Chepalungu Technical Training Institute', 'Chepalungu, Bomet', 'CTTI', True),
    ('Chepsirei Technical And Vocational College', 'Chepsirei, Uasin Gishu', 'CHITVC', True),
    ('Cherangany Technical And Vocational College', 'Cherangany, Trans Nzoia', 'CGTVC', True),
    ('Chuka Technical And Vocational College', 'Chuka, Tharaka Nithi', 'CKTVC', True),
    ('Co-Operative University Of Kenya', 'Nairobi', 'CUK', True),
    ('Coast Institute Of Technology', 'Mombasa', 'CIT', True),
    ('Dr. Daniel Wako Murende Technical & Vocational College', 'Samburu', 'DWMTVC', True),
    ('East African School Of Aviation', 'Nairobi', 'EASA', True),
    ('Ebukanga Technical And Vocational College', 'Ebukanga, Kakamega', 'EBTVC', True),
    ('Ekerubo Gietai Technical Training Institute', 'Ekerubo, Kisii', 'EGTTI', True),
    ('Eldama Ravine Technical And Vocational College', 'Eldama Ravine, Baringo', 'ERTVC', True),
    ('Eldoret Polytechnic', 'Eldoret', 'EP', True),
    ('Elwak Technical And Vocational College', 'Elwak, Mandera', 'EWTVC', True),
    ('Emgwen Technical & Vocational College', 'Emgwen, Nandi', 'EMTVC', True),
    ('Emsos Technical And Vocational College', 'Emsos, Elgeyo-Marakwet', 'ESTVC', True),
    ('Emurua Dikirr Technical Training Institute', 'Emurua Dikirr, Narok', 'EDTTI', True),
    ('Endebess Technical Training Institute', 'Endebess, Trans Nzoia', 'ETTI', True),
    ('Fayya Technical And Vocational College', 'Fayya, Tana River', 'FTVC', True),
    ('Friends College Kaimosi', 'Vihiga', 'FCK', False),
    ('Gatanga Technical And Vocational College', 'Gatanga, Murang\'a', 'GATVC', True),
    ('Gatundu South Technical And Vocational College', 'Gatundu South, Kiambu', 'GSTVC', True),
    ('Githunguri Technical & Vocational College', 'Githunguri, Kiambu', 'GITVC', True),
    ('Gitwebe Technical Training Institute', 'Gitwebe, Nyeri', 'GITTI', True),
    ('Godoma Technical Training Institute', 'Godoma, Tana River', 'GOTTI', True),
    ('Heroes Technical And Vocational College', 'Nairobi', 'HTVC', False),
    ('Ijara Technical & Vocational College', 'Ijara, Garissa', 'IJTVC', True),
    ('Ikutha Technical And Vocational College', 'Ikutha, Kitui', 'IKTVC', True),
    ('Jaramogi Oginga Odinga University Of Science And Technology', 'Bondo, Siaya', 'JOOUST', True),
    ('Jomo Kenyatta University Of Agriculture And Technology Tvet Institute', 'Juja, Kiambu', 'JKUATTI', True),
    ('Kabete National Polytechnic', 'Kabete, Nairobi', 'KNP', True),
    ('Kaelo Technical Training Institute', 'Kaelo, West Pokot', 'KATTI', True),
    ('Kaiboi Technical Training Institute', 'Kaiboi, Nandi', 'KBTTI', True),
    ('Kajiado East Technical & Vocational College', 'Kajiado East', 'KETVC', True),
    ('Kajiado West Technical And Vocational College', 'Kajiado West', 'KWTVC', True),
    ('Kakrao Technical & Vocational College', 'Kakrao, Migori', 'KKTVC', True),
    ('Kamukunji Technical Vocational College', 'Kamukunji, Nairobi', 'KAMTVC', True),
    ('Kandara Technical And Vocational College', 'Kandara, Murang\'a', 'KATVC', True),
    ('Kapchepkor Technical Training Institute', 'Kapchepkor, Elgeyo-Marakwet', 'KCTTI', True),
    ('Kapcherop Technical And Vocational College', 'Kapcherop, Elgeyo-Marakwet', 'KPTVC', True),
    ('Karen Technical Training Institute For The Deaf', 'Karen, Nairobi', 'KTTID', True),
    ('Karumo Technical Training Institute', 'Karumo, Meru', 'KRTTI', True),
    ('Kasarani Technical And Vocational College', 'Kasarani, Nairobi', 'KASTVC', True),
    ('Kendege Technical And Vocational College', 'Kendege, Kisii', 'KDTVC', True),
    ('Kenya Coast Polytechnic', 'Mombasa', 'KCP', True),
    ('Kenya Forestry College', 'Londiani, Kericho', 'KFC', True),
    ('Kenya Industrial Training Institute', 'Nairobi', 'KITI', True),
    ('Kenya Institute Of Highways And Building Technology', 'Nairobi', 'KIHBT', True),
    ('Kenya Institute Of Mass Communication', 'Nairobi', 'KIMC', True),
    ('Kenya Institute Of Surveying And Mapping', 'Nairobi', 'KISM', True),
    ('Kenya School Of Agriculture', 'Kabete, Nairobi', 'KSA', True),
    ('Kenya School Of Revenue Administration', 'Nairobi', 'KESRA', True),
    ('Kenya Water Institute', 'Nairobi', 'KEWI', True),
    ('Kenya Wildlife Service Training Institute', 'Naivasha', 'KWSTI', True),
    ('Kericho Township Technical & Vocational College', 'Kericho', 'KTTVC', True),
    ('Kerio Valley Technical & Vocational College', 'Kerio Valley, Baringo', 'KVTVC', True),
    ('Keroka Technical Training Institute', 'Keroka, Kisii', 'KKTTI', True),
    ('Khwisero Technical & Vocational College', 'Khwisero, Kakamega', 'KHTVC', True),
    ('Kiambu Institute Of Science And Technology', 'Kiambu', 'KIST', True),
    ('Kibwezi Technical & Vocational College', 'Kibwezi, Makueni', 'KBWTVC', True),
    ('Kieni Technical And Vocational College', 'Kieni, Nyeri', 'KITVC', True),
    ('Kigumo Technical Training Institute', 'Kigumo, Murang\'a', 'KGTTI', True),
    ('Kiharu Technical And Vocational College', 'Kiharu, Murang\'a', 'KHTVC2', True),
    ('Kiirua Technical Training Institute', 'Kiirua, Meru', 'KIRTTI', True),
    ('Kimasian Technical And Vocational College', 'Kimasian, Nandi', 'KMTVC', True),
    ('Kinango Technical And Vocational College', 'Kinango, Kwale', 'KNTVC', True),
    ('Kinangop Technical And Vocational College', 'Kinangop, Nyandarua', 'KGPTVC', True),
    ('Kipipiri Technical And Vocational College', 'Kipipiri, Nyandarua', 'KPPTVC', True),
    ('Kipkabus Technical And Vocational College', 'Kipkabus, Uasin Gishu', 'KPKTVC', True),
    ('Kipsinende Technical Vocational College', 'Kipsinende, Nandi', 'KPSTVC', True),
    ('Kipsoen Technical And Vocational College', 'Kipsoen, Kericho', 'KPOTVC', True),
    ('Kiptaragon Technical And Vocational College', 'Kiptaragon, Elgeyo-Marakwet', 'KPTTVC', True),
    ('Kirinyaga Central Technical Vocational College', 'Kirinyaga', 'KCTVC', True),
    ('Kisii National Polytechnic', 'Kisii', 'KisiNP', True),
    ('Kisumu Polytechnic', 'Kisumu', 'KPoly', True),
    ('Kitale National Polytechnic', 'Kitale', 'KiNP', True),
    ('Kitelakapel Technical Training Institute', 'Kitelakapel, West Pokot', 'KPTTI', True),
    ('Kitutu Chache Technical Vocational College', 'Kitutu Chache, Kisii', 'KCTVC2', True),
    ('Kitutu Masaba Technical And Vocational College', 'Kitutu Masaba, Kisii', 'KMTVC2', True),
    ('Kongoni Technical And Vocational College', 'Kongoni, Nyandarua', 'KOTVC', True),
    ('Konoin Technical Training Institute', 'Konoin, Bomet', 'KNTTI', True),
    ('Koshin Technical Training Institute', 'Koshin, Marsabit', 'KOSTI', True),
    ('Laikipia East Technical And Vocational College', 'Laikipia East', 'LETVC', True),
    ('Laikipia North Technical And Vocational College', 'Laikipia North', 'LNTVC', True),
    ('Laikipia University', 'Nyahururu', 'LU', True),
    ('Laikipia University Tvet Institute', 'Nyahururu', 'LUTI', True),
    ('Laikipia West Technical & Vocational College', 'Laikipia West', 'LWTVC', True),
    ('Laisamis Technical And Vocational College', 'Laisamis, Marsabit', 'LTVC', True),
    ('Langata Technical & Vocational College', 'Lang\'ata, Nairobi', 'LGTVC', True),
    ('Lari Technical And Vocational College', 'Lari, Kiambu', 'LATVC', True),
    ('Likoni Technical And Vocational College', 'Likoni, Mombasa', 'LITVC', True),
    ('Limuru Technical And Vocational College', 'Limuru, Kiambu', 'LITVC2', True),
    ('Lodwar Technical And Vocational College', 'Lodwar, Turkana', 'LOTVC', True),
    ('Lunga Lunga Technical And Vocational College', 'Lunga Lunga, Kwale', 'LLTVC', True),
    ('Maasai Mara Technical Vocational College', 'Narok', 'MMTVC', True),
    ('Mabera Technical And Vocational College', 'Mabera, Kisii', 'MBTVC', True),
    ('Machakos Technical Institute For The Blind', 'Machakos', 'MTIB', True),
    ('Machakos University', 'Machakos', 'MUK2', True),
    ('Mandera Technical Training Institute', 'Mandera', 'MDTTI', True),
    ('Manyatta Technical And Vocational College', 'Manyatta, Embu', 'MATVC', True),
    ('Masai Technical Training Institute', 'Kajiado', 'MSTI', True),
    ('Masinde Muliro University Of Science & Technology', 'Kakamega', 'MMUST', True),
    ('Masinga Technical And Vocational College', 'Masinga, Machakos', 'MSTVC', True),
    ('Mathenge Technical Training Institute', 'Mathenge, Nyeri', 'MGTTI', True),
    ('Mathioya Technical Vocational College', 'Mathioya, Murang\'a', 'MHTVC', True),
    ('Mathira Technical And Vocational College', 'Mathira, Nyeri', 'MHTVC2', True),
    ('Matili Technical Training Institute', 'Matili, Kakamega', 'MTTI', True),
    ('Mawego Technical Training Institute', 'Mawego, Homa Bay', 'MWTTI', True),
    ('Mbeere North Technical And Vocational College', 'Mbeere North, Embu', 'MNTVC', True),
    ('Merti Technical And Vocational College', 'Merti, Isiolo', 'METVC', True),
    ('Meru National Polytechnic', 'Meru', 'MNP', True),
    ('Meru University Of Science And Technology', 'Meru', 'MUST', True),
    ('Michuki Technical Training Institute', 'Michuki, Murang\'a', 'MKTTI', True),
    ('Mitunguu Technical Training Institute', 'Mitunguu, Meru', 'MTTTI', True),
    ('Mochongoi Technical And Vocational College', 'Mochongoi, Baringo', 'MCTVC', True),
    ('Moiben Technical Vocational College', 'Moiben, Uasin Gishu', 'MOVTVC', True),
    ('Molo Technical & Vocational College', 'Molo, Nakuru', 'MOTVC', True),
    ('Morendat Institute Of Oil And Gas', 'Naivasha', 'MIOG', True),
    ('Msambweni Technical And Vocational College', 'Msambweni, Kwale', 'MSTVC2', True),
    ('Mukiria Technical Training Institute', 'Mukiria, Meru', 'MKRTTI', True),
    ('Mukurweini Technical Training Institute', 'Mukurweini, Nyeri', 'MKWTTI', True),
    ('Mulango Technical & Vocational College', 'Mulango, Kitui', 'MLTVC', True),
    ('Multimedia University Of Kenya', 'Nairobi', 'MMU', True),
    ('Mumias West Technical Vocational College', 'Mumias West, Kakamega', 'MWTVC', True),
    ('Mungatsi Technical & Vocational College', 'Mungatsi, Vihiga', 'MNTVC2', True),
    ('Muraga Technical And Vocational College', 'Muraga, Nyeri', 'MRTVC', True),
    ('Musakasa Technical Training Institute', 'Musakasa, Kakamega', 'MSTTI', True),
    ('Mwala Technical & Vocational College', 'Mwala, Machakos', 'MWTVC2', True),
    ('Mwea Technical & Vocational College', 'Mwea, Kirinyaga', 'MWTVC3', True),
    ('Nachu Technical And Vocational College', 'Nachu, Kiambu', 'NCTVC', True),
    ('Nairobi Technical Training Institute', 'Nairobi', 'NTTI', True),
    ('Naivasha Technical And Vocational College', 'Naivasha, Nakuru', 'NVTVC', True),
    ('Narok West Technical Training Institute', 'Narok West', 'NWTTI', True),
    ('Navakholo Technical & Vocational College', 'Navakholo, Kakamega', 'NATVC', True),
    ('Ndaragwa Technical And Vocational College', 'Ndaragwa, Nyandarua', 'NDTVC', True),
    ('Ndia Technical And Vocational College', 'Ndia, Kirinyaga', 'NDATVC', True),
    ('Ngong Technical And Vocational College', 'Ngong, Kajiado', 'NGTVC', True),
    ('Nkabune Technical Training Institute', 'Nkabune, Meru', 'NKTTI', True),
    ('North Eastern National Polytechnic', 'Garissa', 'NENP', True),
    ('North Horr Technical & Vocational College', 'North Horr, Marsabit', 'NHTVC', True),
    ('North Rift Technical & Vocational College', 'Turbo, Uasin Gishu', 'NRTVC', True),
    ('Nuu Technical And Vocational College', 'Nuu, Kitui', 'NUTVC', True),
    ('Nyakach Technical And Vocational College', 'Nyakach, Kisumu', 'NYKTVC', True),
    ('Nyandarua National Polytechnic', 'Nyandarua', 'NyNP', True),
    ('Nyeri National Polytechnic', 'Nyeri', 'NNP', True),
    ('Okame Technical And Vocational College', 'Okame, Homa Bay', 'OKTVC', True),
    ('Omuga Technical And Vocational College', 'Omuga, Siaya', 'OMTVC', True),
    ('Orogare Technical And Vocational College', 'Orogare, Kisii', 'ORTVC', True),
    ('Pc Kinyanjui Technical Training Institute', 'Nairobi', 'PCKTTI', True),
    ('Pwani University', 'Kilifi', 'PU', True),
    ('Rachuonyo Technical And Vocational College', 'Rachuonyo, Homa Bay', 'RATVC', True),
    ('Railway Training Institute', 'Nairobi', 'RTI', True),
    ('Ramogi Institute Of Advance Technology', 'Kisumu', 'RIAT', True),
    ('Rangwe Technical And Vocational College', 'Rangwe, Homa Bay', 'RGTVC', True),
    ('Rarieda Technical & Vocational College', 'Rarieda, Siaya', 'RRTVC', True),
    ('Regional Centre For Mapping Of Resources For Development', 'Nairobi', 'RCMRD', True),
    ('Riamo Technical Vocational College', 'Riamo, Homa Bay', 'RITVC', True),
    ('Rift Valley Institute Of Science And Technology', 'Nakuru', 'RVIST', True),
    ('Rift Valley Technical Training Institute', 'Nakuru', 'RVTTI', True),
    ('Riragia Technical Training Institute', 'Riragia, Nyeri', 'RRTTI', True),
    ('Rongo University', 'Migori', 'RU', True),
    ('Ruiru Technical And Vocational College', 'Ruiru, Kiambu', 'RUTVC', True),
    ('Runyenjes Technical And Vocational College', 'Runyenjes, Embu', 'RNTVC', True),
    ('Sabatia Technical And Vocational College', 'Sabatia, Vihiga', 'SATVC', True),
    ('Seku Directorate Of Tvet Wote Campus', 'Wote, Makueni', 'SDTWC', True),
    ('Shamberere Technical Training Institute', 'Shamberere, Kakamega', 'STTI', True),
    ('Siala Technical Training Institute', 'Siala, Siaya', 'SLTTI', True),
    ('Siaya Institute Of Technology', 'Siaya', 'SIT', True),
    ('Sigalagala National Polytechnic', 'Sigalagala, Kakamega', 'SNP', True),
    ('Sikri Technical Training Institute For The Blind And Deaf', 'Bungoma', 'STTIBD', True),
    ('Sirisia Technical And Vocational College', 'Sirisia, Bungoma', 'SITVC', True),
    ('Sot Technical Training Institute', 'Sot, Elgeyo-Marakwet', 'SOTTI', True),
    ('South Eastern Kenya University', 'Kitui', 'SEKU', True),
    ('Tana River Technical & Vocational College', 'Tana River', 'TRTVC', True),
    ('Taveta Technical And Vocational College', 'Taveta, Taita-Taveta', 'TATVC', True),
    ('Technical University Of Kenya', 'Nairobi', 'TUK', True),
    ('Technical University Of Mombasa', 'Mombasa', 'TUM', True),
    ('Tetu Technical And Vocational College', 'Tetu, Nyeri', 'TETVC', True),
    ('Tharaka Technical And Vocational College', 'Tharaka, Tharaka Nithi', 'THTVC', True),
    ('Tharaka University', 'Tharaka', 'TU', True),
    ('Tharaka University Tvet Institute', 'Tharaka', 'TUTI', True),
    ('The Bungoma National Polytechnic', 'Bungoma', 'BNP', True),
    ('The Cuk Nairobi Cbd Training Institute', 'Nairobi', 'CNBDTI', True),
    ('The University Of Embu Tvet Institute', 'Embu', 'UETI', True),
    ('Thika Technical Training Institute', 'Thika, Kiambu', 'TTTI', True),
    ('Tigania East Technical & Vocational College', 'Tigania East, Meru', 'TETVC2', True),
    ('Tindiret Technical And Vocational College', 'Tindiret, Nandi', 'TITVC', True),
    ('Total Technical And Vocational College', 'Nairobi', 'TTVC', False),
    ('Tseikuru Technical Training Institute', 'Tseikuru, Kitui', 'TSKTTI', True),
    ('Turbo Technical & Vocational College', 'Turbo, Uasin Gishu', 'TUTVC', True),
    ('Turkana East Technical And Vocational College', 'Turkana East', 'TETVC3', True),
    ('Turkana University College', 'Lodwar', 'TUC', True),
    ('Ugenya Technical And Vocational College', 'Ugenya, Siaya', 'UGTVC', True),
    ('Ugunja Technical And Vocational College', 'Ugunja, Siaya', 'UJTVC', True),
    ('Uriri Technical And Vocational College', 'Uriri, Migori', 'URTVC', True),
    ('Wajir East Technical & Vocational College', 'Wajir East', 'WETVC', True),
    ('Wanga Technical And Vocational College', 'Wanga, Kakamega', 'WATVC', True),
    ('Webuye West Technical And Vocational College', 'Webuye West, Bungoma', 'WWTVC', True),
    ('Weru Technical And Vocational College', 'Weru, Tharaka Nithi', 'WETVC2', True),
    ('Wote Technical Training Institute', 'Wote, Makueni', 'WTTI', True),
    ('Wumingu Technical & Vocational College', 'Wumingu, Kakamega', 'WMTVC', True),
    ('Ziwa Technical Training Institute', 'Ziwa, Nyeri', 'ZTTTI', True),
]

# Name variants in raw data → canonical institution names used above
INSTITUTION_NAME_MAP = {
    'Ikutha Technical  And Vocational College': 'Ikutha Technical And Vocational College',
    'Kirinyaga Central Technical& Vocational College': 'Kirinyaga Central Technical Vocational College',
    'Kitutu Chache  Technical & Vocational College': 'Kitutu Chache Technical Vocational College',
    'Limuru  Technical And Vocational College': 'Limuru Technical And Vocational College',
    'Mwea  Technical & Vocational College': 'Mwea Technical & Vocational College',
}


# ─────────────────────────────────────────────────────────────────────────────
# 2.  TVET COURSE TYPES — one per qualification level
#     (name, slug, description, icon, color)
# ─────────────────────────────────────────────────────────────────────────────
TVET_COURSE_TYPES = [
    ('TVET Diploma (Level 6)', 'tvet-diploma-level-6',
     'TVET Diploma programmes — highest TVET qualification, KNQF Level 6. Minimum mean grade C-.',
     'bi-award-fill', '#059669'),
    ('TVET Certificate (Level 5)', 'tvet-certificate-level-5',
     'TVET Certificate programmes — KNQF Level 5. Minimum mean grade D+.',
     'bi-patch-check-fill', '#0891b2'),
    ('TVET Artisan Certificate (Level 4)', 'tvet-artisan-level-4',
     'Artisan Certificate — KNQF Level 4. Minimum mean grade D.',
     'bi-hammer', '#d97706'),
    ('TVET Craft Certificate (Level 3)', 'tvet-craft-level-3',
     'Craft Certificate — KNQF Level 3. Minimum mean grade D-.',
     'bi-tools', '#7c3aed'),
    ('TVET Short Course', 'tvet-short-course',
     'Short skills-based TVET courses, typically under one year.',
     'bi-clock-fill', '#dc2626'),
    ('TVET Trade Test', 'tvet-trade-test',
     'Trade tests for occupational competencies.',
     'bi-clipboard2-check-fill', '#1d4ed8'),
    ('TVET Proficiency', 'tvet-proficiency',
     'Proficiency certificates in specific vocational skills.',
     'bi-star-fill', '#6d28d9'),
    ('TVET Professional', 'tvet-professional',
     'Professional TVET qualifications.',
     'bi-briefcase-fill', '#0f766e'),
]


# ─────────────────────────────────────────────────────────────────────────────
# 3.  CANONICAL PROGRAMMES
#     Key: canonical programme name
#     Value: (trade_category, minimum_mean_grade, subject_requirements)
#     subject_requirements: list of {slot, subjects_str, min_grade}
# ─────────────────────────────────────────────────────────────────────────────
_NO_REQS = []

PROGRAMMES = {
    # ── Business & Commerce ────────────────────────────────────────────────
    'Diploma in Accountancy': ('Business & Commerce', 'C-', _NO_REQS),
    'Diploma in Banking & Finance': ('Business & Commerce', 'C-', _NO_REQS),
    'Diploma in Business Management': ('Business & Commerce', 'C-', _NO_REQS),
    'Diploma in Sales & Marketing': ('Business & Commerce', 'C-', _NO_REQS),
    'Diploma in Supply Chain Management': ('Business & Commerce', 'C-', _NO_REQS),
    'Diploma in Procurement & Supply Chain Management': ('Business & Commerce', 'C-', _NO_REQS),
    'Diploma in Human Resource Management': ('Business & Commerce', 'C-', _NO_REQS),
    'Diploma in Co-operative Management': ('Business & Commerce', 'C-', _NO_REQS),
    'Diploma in Secretarial Studies': ('Business & Commerce', 'C-', _NO_REQS),
    'Diploma in Credit Management': ('Business & Commerce', 'C-', _NO_REQS),
    'Diploma in Tax Administration': ('Business & Commerce', 'C', _NO_REQS),
    'Diploma in Customs Administration': ('Business & Commerce', 'C', _NO_REQS),
    'Diploma in Entrepreneurship': ('Business & Commerce', 'C-', _NO_REQS),
    'Diploma in Project Management': ('Business & Commerce', 'C-', _NO_REQS),
    'Diploma in Corporate Governance': ('Business & Commerce', 'C-', _NO_REQS),
    'Diploma in Applied Statistics': ('Business & Commerce', 'C-', _NO_REQS),
    'Diploma in Liberal Studies & Management': ('Business & Commerce', 'C-', _NO_REQS),
    'Diploma in Office Administration': ('Business & Commerce', 'C-', _NO_REQS),
    'Diploma in Public Relations': ('Business & Commerce', 'C-', _NO_REQS),
    # ── Computing & ICT ───────────────────────────────────────────────────
    'Diploma in Information Communication Technology (ICT)': ('Computing & ICT', 'C-', _NO_REQS),
    'Diploma in Computer Science': ('Computing & ICT', 'C-', _NO_REQS),
    'Diploma in Software Development': ('Computing & ICT', 'C-', _NO_REQS),
    'Diploma in Data Management & Analytics': ('Computing & ICT', 'C-', _NO_REQS),
    'Diploma in Network & Systems Administration': ('Computing & ICT', 'C-', _NO_REQS),
    'Diploma in Graphic Design': ('Computing & ICT', 'C-', _NO_REQS),
    'Diploma in Animation & Graphics Design': ('Computing & ICT', 'C-', _NO_REQS),
    'Diploma in Information Science': ('Computing & ICT', 'C-', _NO_REQS),
    'Diploma in Media Technology': ('Computing & ICT', 'C-', _NO_REQS),
    # ── Engineering & Technology ──────────────────────────────────────────
    'Diploma in Electrical & Electronics Engineering (Power)': ('Engineering & Technology', 'C-', _NO_REQS),
    'Diploma in Electrical & Electronics Engineering (Telecommunication)': ('Engineering & Technology', 'C-', _NO_REQS),
    'Diploma in Electrical & Electronics Engineering (Instrumentation)': ('Engineering & Technology', 'C-', _NO_REQS),
    'Diploma in Mechanical Engineering (Automotive)': ('Engineering & Technology', 'C-', _NO_REQS),
    'Diploma in Mechanical Engineering (Plant)': ('Engineering & Technology', 'C-', _NO_REQS),
    'Diploma in Mechanical Engineering (Production)': ('Engineering & Technology', 'C-', _NO_REQS),
    'Diploma in Civil Engineering': ('Engineering & Technology', 'C-', _NO_REQS),
    'Diploma in Civil Engineering (Roads & Highways)': ('Engineering & Technology', 'C-', _NO_REQS),
    'Diploma in Building & Construction Technology': ('Engineering & Technology', 'C-', _NO_REQS),
    'Diploma in Automotive Engineering': ('Engineering & Technology', 'C-', _NO_REQS),
    'Diploma in Welding & Fabrication': ('Engineering & Technology', 'C-', _NO_REQS),
    'Diploma in Chemical Engineering': ('Engineering & Technology', 'C-', _NO_REQS),
    'Diploma in Mechatronics': ('Engineering & Technology', 'C-', _NO_REQS),
    'Diploma in Refrigeration & Air Conditioning': ('Engineering & Technology', 'C-', _NO_REQS),
    'Diploma in Marine Engineering': ('Engineering & Technology', 'C-', _NO_REQS),
    'Diploma in Telecommunication Engineering': ('Engineering & Technology', 'C-', _NO_REQS),
    'Diploma in Construction Management': ('Engineering & Technology', 'C-', _NO_REQS),
    'Diploma in Construction Plant Engineering': ('Engineering & Technology', 'C-', _NO_REQS),
    'Diploma in Plant & Services Engineering': ('Engineering & Technology', 'C-', _NO_REQS),
    'Diploma in Agricultural Engineering': ('Engineering & Technology', 'C-', _NO_REQS),
    'Diploma in Irrigation & Drainage Engineering': ('Engineering & Technology', 'C-', [
        {'slot': 1, 'subjects_str': 'ENG/KIS', 'min_grade': 'D'},
        {'slot': 2, 'subjects_str': 'MAT A', 'min_grade': 'D'},
        {'slot': 3, 'subjects_str': 'PHY/CHE', 'min_grade': 'D'},
        {'slot': 4, 'subjects_str': 'BIO/GEO/HSC/AGR/BST', 'min_grade': 'C-'},
    ]),
    'Diploma in Water Engineering & Technology': ('Engineering & Technology', 'C-', _NO_REQS),
    'Diploma in Aeronautical Engineering (Airframes & Engines)': ('Engineering & Technology', 'C', [
        {'slot': 1, 'subjects_str': 'MAT A', 'min_grade': 'C-'},
        {'slot': 2, 'subjects_str': 'ENG', 'min_grade': 'C-'},
        {'slot': 3, 'subjects_str': 'PHY', 'min_grade': 'C-'},
    ]),
    'Diploma in Aeronautical Engineering (Avionics)': ('Engineering & Technology', 'C', [
        {'slot': 1, 'subjects_str': 'MAT A', 'min_grade': 'C-'},
        {'slot': 2, 'subjects_str': 'ENG', 'min_grade': 'C-'},
        {'slot': 3, 'subjects_str': 'PHY', 'min_grade': 'C-'},
    ]),
    'Diploma in Printing Technology': ('Engineering & Technology', 'C-', _NO_REQS),
    # ── Built Environment ──────────────────────────────────────────────────
    'Diploma in Architecture': ('Built Environment', 'C', [
        {'slot': 1, 'subjects_str': 'MAT A', 'min_grade': 'C'},
        {'slot': 2, 'subjects_str': 'PHY', 'min_grade': 'C'},
        {'slot': 3, 'subjects_str': 'ENG/KIS', 'min_grade': 'C'},
    ]),
    'Diploma in Quantity Surveying': ('Built Environment', 'C', [
        {'slot': 1, 'subjects_str': 'MAT A', 'min_grade': 'C'},
        {'slot': 2, 'subjects_str': 'PHY', 'min_grade': 'C'},
        {'slot': 3, 'subjects_str': 'ENG/KIS', 'min_grade': 'C'},
    ]),
    'Diploma in Land Surveying': ('Built Environment', 'C-', [
        {'slot': 1, 'subjects_str': 'ENG/KIS', 'min_grade': 'C-'},
        {'slot': 2, 'subjects_str': 'MAT A', 'min_grade': 'C-'},
        {'slot': 3, 'subjects_str': 'PHY', 'min_grade': 'C-'},
    ]),
    'Diploma in Photogrammetry & Remote Sensing': ('Built Environment', 'C-', [
        {'slot': 1, 'subjects_str': 'ENG', 'min_grade': 'C-'},
        {'slot': 2, 'subjects_str': 'MAT A', 'min_grade': 'C-'},
        {'slot': 3, 'subjects_str': 'PHY', 'min_grade': 'C-'},
    ]),
    'Diploma in Cartography': ('Built Environment', 'C-', [
        {'slot': 1, 'subjects_str': 'ENG', 'min_grade': 'C-'},
        {'slot': 2, 'subjects_str': 'MAT A', 'min_grade': 'C-'},
        {'slot': 3, 'subjects_str': 'GEO', 'min_grade': 'C-'},
    ]),
    # ── Health Sciences ────────────────────────────────────────────────────
    'Diploma in Medical Laboratory Sciences': ('Health Sciences', 'C', [
        {'slot': 1, 'subjects_str': 'ENG/KIS', 'min_grade': 'C'},
        {'slot': 2, 'subjects_str': 'MAT A/PHY', 'min_grade': 'C'},
        {'slot': 3, 'subjects_str': 'BIO', 'min_grade': 'C'},
        {'slot': 4, 'subjects_str': 'CHE', 'min_grade': 'C'},
    ]),
    'Diploma in Community Health': ('Health Sciences', 'C', [
        {'slot': 1, 'subjects_str': 'ENG/KIS', 'min_grade': 'C'},
        {'slot': 2, 'subjects_str': 'MAT A/MAT B', 'min_grade': 'C-'},
        {'slot': 3, 'subjects_str': 'BIO/BSC', 'min_grade': 'D+'},
        {'slot': 4, 'subjects_str': 'PHY/CHE/COMP/AGR/HSC/ECON/GEO/COM/BST', 'min_grade': 'C-'},
    ]),
    'Diploma in Nutrition & Dietetics': ('Health Sciences', 'C-', [
        {'slot': 1, 'subjects_str': 'ENG/KIS', 'min_grade': 'C-'},
        {'slot': 2, 'subjects_str': 'MAT A', 'min_grade': 'C-'},
        {'slot': 3, 'subjects_str': 'PHY', 'min_grade': 'C-'},
    ]),
    'Diploma in Environmental Health Sciences': ('Health Sciences', 'C', [
        {'slot': 1, 'subjects_str': 'ENG/KIS', 'min_grade': 'C'},
        {'slot': 2, 'subjects_str': 'BIO/BSC', 'min_grade': 'C'},
        {'slot': 3, 'subjects_str': 'CHE/PHY/PSC', 'min_grade': 'C-'},
    ]),
    'Diploma in Medical Engineering': ('Health Sciences', 'C-', _NO_REQS),
    'Diploma in Pharmaceutical Technology': ('Health Sciences', 'C', [
        {'slot': 1, 'subjects_str': 'CHE', 'min_grade': 'C'},
        {'slot': 2, 'subjects_str': 'BIO', 'min_grade': 'C'},
        {'slot': 3, 'subjects_str': 'MAT A/PHY', 'min_grade': 'C'},
        {'slot': 4, 'subjects_str': 'ENG/KIS', 'min_grade': 'C'},
    ]),
    'Diploma in Health Records & Information Technology': ('Health Sciences', 'C', [
        {'slot': 1, 'subjects_str': 'ENG/KIS', 'min_grade': 'C'},
        {'slot': 2, 'subjects_str': 'MAT A/MAT B', 'min_grade': 'C-'},
        {'slot': 3, 'subjects_str': 'BIO/BSC', 'min_grade': 'D+'},
        {'slot': 4, 'subjects_str': 'PHY/CHE/COMP/AGR/HSC/ECON/GEO/COM/BST', 'min_grade': 'C-'},
    ]),
    'Diploma in Science Laboratory Technology': ('Health Sciences', 'C-', _NO_REQS),
    # ── Agriculture ────────────────────────────────────────────────────────
    'Diploma in General Agriculture': ('Agriculture', 'C-', _NO_REQS),
    'Diploma in Horticulture Production': ('Agriculture', 'C-', _NO_REQS),
    'Diploma in Animal Health & Production': ('Agriculture', 'C', [
        {'slot': 1, 'subjects_str': 'BIO', 'min_grade': 'C'},
        {'slot': 2, 'subjects_str': 'CHE', 'min_grade': 'C-'},
        {'slot': 3, 'subjects_str': 'MAT A/PHY/AGR', 'min_grade': 'C-'},
    ]),
    'Diploma in Agribusiness Management': ('Agriculture', 'C-', _NO_REQS),
    'Diploma in Agricultural Extension': ('Agriculture', 'C-', _NO_REQS),
    'Diploma in Agripreneurship': ('Agriculture', 'C-', _NO_REQS),
    'Diploma in Farm Business Management': ('Agriculture', 'C-', _NO_REQS),
    'Diploma in Fisheries & Aquatic Sciences': ('Agriculture', 'C-', _NO_REQS),
    'Diploma in Aquaculture': ('Agriculture', 'C-', _NO_REQS),
    'Diploma in Dairy Farm Management': ('Agriculture', 'C-', _NO_REQS),
    'Diploma in Applied Biology': ('Agriculture', 'C-', _NO_REQS),
    'Diploma in Applied Chemistry': ('Agriculture', 'C-', _NO_REQS),
    'Diploma in Analytical Chemistry': ('Agriculture', 'C-', _NO_REQS),
    'Diploma in Industrial Chemistry': ('Agriculture', 'C-', _NO_REQS),
    'Diploma in Food Science & Technology': ('Agriculture', 'C-', _NO_REQS),
    # ── Hospitality & Tourism ──────────────────────────────────────────────
    'Diploma in Catering & Accommodation Management': ('Hospitality & Tourism', 'C-', _NO_REQS),
    'Diploma in Tourism & Hospitality Management': ('Hospitality & Tourism', 'C-', _NO_REQS),
    'Diploma in Tour Guiding': ('Hospitality & Tourism', 'C-', _NO_REQS),
    'Diploma in Food & Beverage Production & Service Management': ('Hospitality & Tourism', 'C-', _NO_REQS),
    'Diploma in Housekeeping & Accommodation Management': ('Hospitality & Tourism', 'C-', _NO_REQS),
    'Diploma in Front Office Operations': ('Hospitality & Tourism', 'C-', _NO_REQS),
    'Diploma in Fitness & Recreation Management': ('Hospitality & Tourism', 'C-', _NO_REQS),
    'Diploma in Baking Technology': ('Hospitality & Tourism', 'C-', _NO_REQS),
    # ── Media & Communications ─────────────────────────────────────────────
    'Diploma in Journalism': ('Media & Communications', 'C-', _NO_REQS),
    'Diploma in Film & Video Production': ('Media & Communications', 'C-', _NO_REQS),
    'Diploma in Television Production': ('Media & Communications', 'C-', _NO_REQS),
    'Diploma in Radio Production & Broadcasting': ('Media & Communications', 'C-', _NO_REQS),
    'Diploma in Library & Information Science': ('Media & Communications', 'C-', _NO_REQS),
    'Diploma in Archives & Records Management': ('Media & Communications', 'C-', _NO_REQS),
    'Diploma in Music & Performing Arts': ('Media & Communications', 'C-', _NO_REQS),
    # ── Social Sciences ────────────────────────────────────────────────────
    'Diploma in Social Work & Community Development': ('Social Sciences', 'C-', _NO_REQS),
    'Diploma in Community Development': ('Social Sciences', 'C-', _NO_REQS),
    'Diploma in Guidance & Counselling': ('Social Sciences', 'C-', _NO_REQS),
    'Diploma in Early Childhood Education': ('Social Sciences', 'C-', _NO_REQS),
    'Diploma in Criminology & Criminal Justice': ('Social Sciences', 'C-', _NO_REQS),
    'Diploma in Security & Intelligence Studies': ('Social Sciences', 'C-', _NO_REQS),
    'Diploma in Child Care & Protection': ('Social Sciences', 'C-', _NO_REQS),
    'Diploma in Disaster Management': ('Social Sciences', 'C-', _NO_REQS),
    # ── Environment & Natural Resources ────────────────────────────────────
    'Diploma in Environmental Science & Technology': ('Environment & Natural Resources', 'C-', _NO_REQS),
    'Diploma in Nautical Sciences': ('Environment & Natural Resources', 'C-', _NO_REQS),
    'Diploma in Wildlife Management': ('Environment & Natural Resources', 'C-', _NO_REQS),
    'Diploma in Petroleum & Geoscience': ('Environment & Natural Resources', 'C-', _NO_REQS),
    'Diploma in Petroleum Management': ('Environment & Natural Resources', 'C-', _NO_REQS),
    # ── Fashion & Design ───────────────────────────────────────────────────
    'Diploma in Fashion Design & Clothing Technology': ('Fashion & Design', 'C-', _NO_REQS),
    'Diploma in Fashion Design & Garment Making': ('Fashion & Design', 'C-', _NO_REQS),
    'Diploma in Clothing & Textile Technology': ('Fashion & Design', 'C-', _NO_REQS),
    # ── Transport & Logistics ──────────────────────────────────────────────
    'Diploma in Transport Management': ('Transport & Logistics', 'C-', _NO_REQS),
    'Diploma in Shipping & Logistics': ('Transport & Logistics', 'C-', _NO_REQS),
    'Diploma in Air Cargo Management': ('Transport & Logistics', 'C-', _NO_REQS),
    'Diploma in Airport Operations': ('Transport & Logistics', 'C-', _NO_REQS),
    'Diploma in Flight Operations & Dispatch': ('Transport & Logistics', 'C-', _NO_REQS),
    'Diploma in Freight Management': ('Transport & Logistics', 'C-', _NO_REQS),
}


# ─────────────────────────────────────────────────────────────────────────────
# 4.  COMMAND CLASS
# ─────────────────────────────────────────────────────────────────────────────
class Command(BaseCommand):
    help = 'Seed all TVET institutions, programmes, and course offerings from KUCCPS data.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Delete existing TVET institutions and courses before seeding.'
        )

    def handle(self, *args, **options):
        self.stdout.write('-' * 60)
        self.stdout.write('seed_tvet — starting')
        self.stdout.write('-' * 60)

        data_path = os.path.join(os.path.dirname(__file__), 'tvet_data.json')
        with open(data_path, encoding='utf-8') as f:
            raw_offerings = json.load(f)

        with transaction.atomic():
            if options['clear']:
                self._clear_existing()
            pub_type, priv_type = self._ensure_institution_types()
            course_type_map = self._ensure_course_types()
            inst_map = self._seed_institutions(pub_type, priv_type)
            course_map = self._seed_courses(course_type_map)
            self._seed_offerings(inst_map, course_map, raw_offerings)

        self.stdout.write(self.style.SUCCESS('\nDone.'))

    # ── helpers ──────────────────────────────────────────────────────────────

    def _clear_existing(self):
        self.stdout.write('\n[0] Clearing existing TVET data...')
        for type_name in ('Public TVET', 'Private TVET'):
            inst_type = InstitutionType.objects.filter(name=type_name).first()
            if inst_type:
                n, _ = Institution.objects.filter(institution_type=inst_type).delete()
                self.stdout.write(f'  Deleted {n} {type_name} institutions')
        for ct_name, _, _, _, _ in TVET_COURSE_TYPES:
            ct = CourseType.objects.filter(name=ct_name).first()
            if ct:
                n, _ = Course.objects.filter(course_type=ct).delete()
                CourseCategory.objects.filter(course_type=ct).delete()
                self.stdout.write(f'  Cleared {n} courses under {ct_name}')

    def _ensure_institution_types(self):
        pub, _ = InstitutionType.objects.get_or_create(
            name='Public TVET',
            defaults={
                'description': 'Government-funded Technical and Vocational Education and Training institutions',
                'icon': 'bi-tools',
                'color_code': '#059669',
            }
        )
        priv, _ = InstitutionType.objects.get_or_create(
            name='Private TVET',
            defaults={
                'description': 'Privately-owned licensed TVET institutions accredited by TVETA',
                'icon': 'bi-tools',
                'color_code': '#7c3aed',
            }
        )
        self.stdout.write(f'\n[1] Institution types: Public TVET, Private TVET')
        return pub, priv

    def _ensure_course_types(self):
        self.stdout.write('\n[2] TVET course types (one per qualification level)')
        ct_map = {}
        for name, slug, desc, icon, color in TVET_COURSE_TYPES:
            ct, _ = CourseType.objects.update_or_create(
                name=name,
                defaults={
                    'description': desc,
                    'icon': icon,
                    'color_code': color,
                }
            )
            ct_map[name] = ct
        self.stdout.write(f'  {len(ct_map)} course types ensured')
        return ct_map

    def _seed_institutions(self, pub_type, priv_type):
        self.stdout.write('\n[3] Institutions')
        inst_map = {}
        created_count = updated_count = 0

        for name, location, abbrev, is_public in INSTITUTIONS:
            inst_type = pub_type if is_public else priv_type
            try:
                # Look up by name only — institution may already exist under a different type
                inst = Institution.objects.get(name=name)
                inst.institution_type = inst_type
                inst.location = location
                inst.abbreviation = abbrev
                inst.save(update_fields=['institution_type', 'location', 'abbreviation'])
                updated_count += 1
            except Institution.DoesNotExist:
                inst = Institution.objects.create(
                    name=name,
                    institution_type=inst_type,
                    location=location,
                    abbreviation=abbrev,
                    description=f'{"Public" if is_public else "Private"} TVET institution — {location}',
                )
                created_count += 1
            inst_map[name] = inst

        for raw_name, canonical_name in INSTITUTION_NAME_MAP.items():
            if canonical_name in inst_map:
                inst_map[raw_name] = inst_map[canonical_name]

        self.stdout.write(f'  {created_count} created, {updated_count} moved/updated ({len(INSTITUTIONS)} total)')
        return inst_map

    def _seed_courses(self, course_type_map):
        self.stdout.write('\n[4] Courses (canonical programmes)')
        diploma_ct = course_type_map['TVET Diploma (Level 6)']
        course_map = {}
        created_count = updated_count = 0
        trade_cat_cache = {}

        for prog_name, (trade_cat, mean_grade, reqs) in PROGRAMMES.items():
            # Get or create trade-sector category under the Diploma course type
            if trade_cat not in trade_cat_cache:
                cat, _ = CourseCategory.objects.get_or_create(
                    name=trade_cat,
                    course_type=diploma_ct,
                    defaults={'description': f'TVET Diploma — {trade_cat}'}
                )
                trade_cat_cache[trade_cat] = cat
            trade_cat_obj = trade_cat_cache[trade_cat]

            course, created = Course.objects.get_or_create(
                name=prog_name,
                course_type=diploma_ct,
                defaults={
                    'category': trade_cat_obj,
                    'minimum_mean_grade': mean_grade,
                    'subject_requirements': reqs if reqs else None,
                    'description': (
                        f'TVET Diploma (Level 6) — {trade_cat}. '
                        f'Minimum mean grade: {mean_grade}.'
                    ),
                }
            )
            if not created:
                course.minimum_mean_grade = mean_grade
                course.subject_requirements = reqs if reqs else None
                course.category = trade_cat_obj
                course.save(update_fields=['minimum_mean_grade', 'subject_requirements', 'category'])
                updated_count += 1
            else:
                created_count += 1
            course_map[prog_name] = course

        self.stdout.write(f'  {created_count} created, {updated_count} updated ({len(course_map)} total)')
        return course_map

    def _seed_offerings(self, inst_map, course_map, raw_offerings):
        self.stdout.write('\n[5] Offerings (institution × programme links)')
        created = skipped = already = 0

        for entry in raw_offerings:
            institution = inst_map.get(entry['institution'])
            course = course_map.get(entry['programme'])

            if not institution or not course:
                skipped += 1
                continue

            _, was_created = CourseOffering.objects.update_or_create(
                course=course,
                institution=institution,
                defaults={'programme_code': entry['code']}
            )
            if was_created:
                created += 1
            else:
                already += 1

        total = len(raw_offerings)
        self.stdout.write(
            f'  {created} new, {already} already existed, {skipped} skipped'
        )
        self.stdout.write(f'  Total processed: {total - skipped} of {total}')
