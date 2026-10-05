"""
KUCCPS cluster reference data.

KUCCPS groups degree programmes into 18 clusters (the old 20-cluster scheme and its
lettered sub-clusters such as 13A/13B are gone). Each Cluster row numbered
101–118 is KUCCPS cluster (number − 100); degree courses link to these directly.
"""

CALC_CLUSTER_OFFSET = 100

# Official names (students.kuccps.net/programmes), tidied to fit Cluster.name max_length=100
KUCCPS_CLUSTER_NAMES: dict[int, str] = {
    1:  'Law',
    2:  'Business, Hospitality, Tourism & Related',
    3:  'Communication, Media, Languages, International Relations, Film, Graphics & Related',
    4:  'Geosciences & Related',
    5:  'Engineering, Engineering Technology, Energy & Related',
    6:  'Architecture, Quantity Survey, Building Construction, Urban Planning & Related',
    7:  'Computer Science, Cyber Security, Information Technology & Related',
    8:  'Agricultural Economics, Agribusiness & Related',
    9:  'General Sciences, Biological Sciences, Physics, Chemistry & Related',
    10: 'Actuarial Science, Mathematics, Statistics & Related',
    11: 'Interior Design, Fashion Design, Textile & Related',
    12: 'Sports Science & Related',
    13: 'Medicine, Nursing, Dentistry, Pharmacy, Health Sciences & Related',
    14: 'History, Archaeology, Geography & Related',
    15: 'Agriculture, Animal Health, Food Science, Nutrition, Environment & Natural Resources',
    16: 'Music & Related',
    17: 'Education & Related',
    18: 'Religious Studies, Theology, Islamic Studies & Related',
}

NUM_KUCCPS_CLUSTERS = len(KUCCPS_CLUSTER_NAMES)

# Valid Cluster.number values — exactly one row per KUCCPS cluster (101–118)
KUCCPS_CLUSTER_NUMBERS = range(CALC_CLUSTER_OFFSET + 1, CALC_CLUSTER_OFFSET + NUM_KUCCPS_CLUSTERS + 1)
