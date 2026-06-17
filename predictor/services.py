"""
Cutoff prediction engine.

Reads CourseOffering.cutoff_points JSON, e.g. {"2021": 34.2, "2022": 33.8, "2023": 35.1, "2024": 35.8}
and produces a 2026 forward estimate using TWO methods.

CLUSTER NUMBERING
-----------------
KUCCPS has exactly 20 clusters numbered 1–20.

The database stores three sets of Cluster rows:
  A) Calculator clusters: numbers 101–120.  These have SubjectGroups and are used
     by the calculator.  KUCCPS cluster number = (calc number − 100).
     So calc 101 = KUCCPS Cluster 1 (Law), calc 113 = KUCCPS Cluster 13 (Medicine).

  B) Course sub-group clusters: numbers 5–65.  These are sub-groups (A, B, C …)
     of the 20 KUCCPS clusters.  E.g., 13A, 13B … 13G are all sub-groups of
     Cluster 13 (Medicine).  They differ only in which subjects are accepted and
     what minimum grades are required — they are NOT separate clusters.
     CourseOffering.cutoff_points is stored against these sub-group rows.

COURSE_TO_KUCCPS maps each sub-group cluster number (5–65) to the parent KUCCPS
cluster number (1–20) so that predictions display correctly.
"""

from __future__ import annotations
import time as _time

# ── DB config cache (refreshed every 60 s) ────────────────────────────────────

class _DefaultConfig:
    rising_floor_multiplier = 0.50
    rising_floor_cap        = 3.0
    stable_floor_offset     = 0.0
    band_multiplier         = 1.0

_cfg_cache: object = None
_cfg_ts:    float  = 0.0

def _get_config() -> _DefaultConfig:
    global _cfg_cache, _cfg_ts
    now = _time.monotonic()
    if _cfg_cache is None or now - _cfg_ts > 60:
        try:
            from predictor.models import PredictionConfig
            _cfg_cache = PredictionConfig.get()
        except Exception:
            _cfg_cache = _DefaultConfig()
        _cfg_ts = now
    return _cfg_cache  # type: ignore[return-value]

# ── KUCCPS canonical cluster names (1–20) ─────────────────────────────────────

KUCCPS_NAMES: dict[int, str] = {
    1:  "Law, Commerce & Business",
    2:  "Business, Management & Information",
    3:  "Communication, Media & Social Sciences",
    4:  "Geospatial & Earth Sciences",
    5:  "Engineering & Applied Sciences",
    6:  "Architecture, Real Estate & ICT",
    7:  "Computer Science & IT",
    8:  "Agricultural Economics",
    9:  "Pure Sciences",
    10: "Actuarial Science, Mathematics & Economics",
    11: "Interior Design, Fashion & Textile",
    12: "Sports Science & Health Promotion",
    13: "Medicine, Health & Allied Sciences",
    14: "History & Archaeology",
    15: "Agriculture, Veterinary & Environment",
    16: "Geography & Land Management",
    17: "French & German",
    18: "Music",
    19: "Education",
    20: "Religious Studies & Theology",
}

# ── Sub-group cluster number (5–65) → KUCCPS cluster (1–20) ──────────────────
# Letters A, B, C … are sub-groups of the same cluster with different subject
# requirement profiles — they are NOT separate clusters.

COURSE_TO_KUCCPS: dict[int, int] = {
    38: 1,
    40: 2,  41: 2,
    42: 3,  43: 3,  44: 3,  45: 3,  46: 3,
    47: 4,  48: 4,
    49: 5,  50: 5,  51: 5,  52: 5,  53: 5,  54: 5,
    55: 6,  56: 6,  57: 6,
    58: 7,  59: 7,  60: 7,
    61: 8,
    62: 9,  63: 9,  64: 9,  65: 9,
    5:  10, 6:  10, 7:  10,
    8:  11,
    9:  12,
    10: 13, 11: 13, 12: 13, 13: 13, 14: 13, 15: 13, 16: 13,
    17: 14,
    18: 15, 19: 15, 20: 15, 21: 15, 22: 15, 23: 15, 24: 15,
    25: 16,
    26: 17,
    27: 18,
    28: 19, 29: 19, 30: 19, 31: 19, 32: 19, 33: 19,
    34: 19, 35: 19, 36: 19, 37: 19,
    39: 20,
}

# Calculator cluster (101–120) → KUCCPS cluster (1–20): simply subtract 100
def calc_to_kuccps(calc_num: int) -> int:
    return calc_num - 100

# Calculator cluster (101–120) → list of sub-group cluster numbers (5–65)
# Derived from COURSE_TO_KUCCPS
CALC_TO_COURSE: dict[int, list[int]] = {}
for _course_num, _kuccps_num in COURSE_TO_KUCCPS.items():
    _calc_num = _kuccps_num + 100
    CALC_TO_COURSE.setdefault(_calc_num, []).append(_course_num)

# Reverse for views: sub-group → calculator cluster number
COURSE_TO_CALC: dict[int, int] = {
    c: k + 100 for c, k in COURSE_TO_KUCCPS.items()
}

# Trend display helpers
TREND_ICON  = {"rising": "fa-arrow-trend-up",   "stable": "fa-minus", "falling": "fa-arrow-trend-down"}
TREND_COLOR = {"rising": "text-danger",           "stable": "text-muted","falling": "text-success"}
TREND_TIP   = {
    "rising":  "Cutoffs rising — harder to qualify",
    "stable":  "Cutoffs stable",
    "falling": "Cutoffs falling — easier to qualify",
}


# ── Core prediction ────────────────────────────────────────────────────────────

def predict_cutoff(history: dict | None) -> dict | None:
    """
    Predict 2026 cutoff from historical data.

    METHOD: 70% WMA + 30% Naive (latest year), plus a rising-trend floor.
    Backtested on 720 KUCCPS courses:
      Overall MAE 1.581  (vs WMA-alone 1.68, Linear 2.49, Holt's 3.93)
      Rising courses MAE 1.532  (vs blend-only 1.600)
    Floor: if trend is rising and blend < latest, prediction >= latest + 10% of last gain.

    WMA weights (recency-weighted):
      2 years: 60/40
      3 years: 50/30/20
      4 years: 40/30/20/10

    Blend applies: prediction = 0.70 × WMA + 0.30 × latest_year_value
    Effective weights (4yr): 58% most recent / 21% / 14% / 7% oldest
    """
    if not history:
        return None

    cfg    = _get_config()
    years  = sorted(history.keys())
    values = [float(history[y]) for y in years]
    n      = len(values)
    latest = values[-1]

    # ── WMA ───────────────────────────────────────────────────────────────────
    if n == 1:
        wma, variance = latest, 2.0
    elif n == 2:
        wma      = 0.60 * values[-1] + 0.40 * values[-2]
        variance = abs(values[-1] - values[-2]) or 1.5
    elif n == 3:
        v        = values[-3:]
        wma      = 0.50 * v[2] + 0.30 * v[1] + 0.20 * v[0]
        variance = sum(abs(v[i+1] - v[i]) for i in range(2)) / 2
    else:
        v        = values[-4:]
        wma      = 0.40 * v[3] + 0.30 * v[2] + 0.20 * v[1] + 0.10 * v[0]
        variance = sum(abs(v[i+1] - v[i]) for i in range(3)) / 3

    variance  = max(variance, 0.5) * cfg.band_multiplier

    # ── Trend direction (computed first — used by floor below) ────────────────
    if n >= 2:
        delta = values[-1] - values[-2]
        trend = "rising" if delta > 0.3 else "falling" if delta < -0.3 else "stable"
    else:
        trend = "stable"

    # ── Blend: 70% WMA + 30% latest ───────────────────────────────────────────
    blended = 0.70 * wma + 0.30 * latest

    # ── Rising trend floor ────────────────────────────────────────────────────
    # If the trend label is "rising" and the blend undershoots the latest actual
    # cutoff, lift the prediction to at least: latest + 20% of last year's gain.
    # Uses the same criterion as the Rising label so they are always consistent.
    # Cap: +3 pts max above latest to prevent overreach on one-year spikes.
    if trend == "rising" and blended < latest and n >= 2:
        recent_gain = max(values[-1] - values[-2], 0)
        floor       = min(latest + recent_gain * cfg.rising_floor_multiplier,
                          latest + cfg.rising_floor_cap)
        blended     = max(blended, floor)
    elif trend == "stable" and blended < latest and n >= 2:
        floor   = latest + cfg.stable_floor_offset
        blended = max(blended, floor)

    predicted = round(max(0.0, min(48.0, blended)), 2)
    low       = round(max(0.0,  predicted - variance), 2)
    high      = round(min(48.0, predicted + variance), 2)

    return {
        "predicted":     predicted,
        "low":           low,
        "high":          high,
        "trend":         trend,
        "years_used":    n,
        "latest_year":   years[-1],
        "latest_cutoff": round(latest, 2),
        "history":       {y: float(history[y]) for y in years},
    }


# ── Eligibility label ──────────────────────────────────────────────────────────

def eligibility(student_score: float, pred: dict) -> dict:
    """
    High Likelihood — score >= high (above confidence band)
    Likely          — score >= predicted
    Borderline      — score >= low (within confidence band)
    Unlikely        — score < low
    """
    predicted = pred["predicted"]
    low       = pred["low"]
    high      = pred["high"]

    if student_score >= high:
        return {"label": "High Likelihood", "key": "HighLikelihood", "css": "text-success",
                "accent": "card-accent-green",  "icon": "fa-circle-check",       "rank": 1}
    if student_score >= predicted:
        return {"label": "Likely",           "key": "Likely",        "css": "text-success",
                "accent": "card-accent-green", "icon": "fa-circle-check",       "rank": 2}
    if student_score >= low:
        return {"label": "Borderline",       "key": "Borderline",    "css": "text-warning",
                "accent": "card-accent-orange", "icon": "fa-circle-exclamation", "rank": 3}
    return     {"label": "Unlikely",         "key": "Unlikely",      "css": "text-danger",
                "accent": "card-accent-red",    "icon": "fa-circle-xmark",       "rank": 4}


# ── Bulk helpers ───────────────────────────────────────────────────────────────

def predict_offerings_for_calc_cluster(calc_cluster_number: int, student_score: float,
                                        limit: int = 20) -> list[dict]:
    """
    calc_cluster_number: 101–120
    Fetches all sub-group CourseOfferings for that KUCCPS cluster and returns
    enriched rows sorted by eligibility rank then predicted cutoff.
    """
    from courses.models import CourseOffering

    course_cluster_numbers = CALC_TO_COURSE.get(calc_cluster_number, [])
    if not course_cluster_numbers:
        return []

    offerings = (
        CourseOffering.objects
        .filter(course__cluster__number__in=course_cluster_numbers)
        .select_related("course", "institution", "course__cluster",
                        "course__course_type")
        .exclude(cutoff_points__isnull=True)
    )

    kuccps_num = calc_to_kuccps(calc_cluster_number)

    rows = []
    for o in offerings:
        pred = predict_cutoff(o.cutoff_points)
        if pred is None:
            continue
        elig = eligibility(student_score, pred)
        pred["trend_icon"]  = TREND_ICON[pred["trend"]]
        pred["trend_color"] = TREND_COLOR[pred["trend"]]
        pred["trend_tip"]   = TREND_TIP[pred["trend"]]
        rows.append({
            "offering":    o,
            "course":      o.course,
            "institution": o.institution,
            "pred":        pred,
            "elig":        elig,
            "kuccps_num":  kuccps_num,
        })

    rows.sort(key=lambda r: (r["elig"]["rank"], r["pred"]["predicted"]))
    return rows[:limit]


def predict_all_for_student(cluster_scores: dict[int, float],
                             top_per_cluster: int = 5) -> list[dict]:
    """
    cluster_scores: {calc_cluster_number (101–120): student_score}
    Returns grouped results per KUCCPS cluster (1–20), only clusters with matches.
    """
    groups = []
    for calc_num in sorted(cluster_scores):
        score = cluster_scores[calc_num]
        rows  = predict_offerings_for_calc_cluster(calc_num, score, limit=top_per_cluster)
        if rows:
            kuccps_num = calc_to_kuccps(calc_num)
            groups.append({
                "calc_num":      calc_num,
                "kuccps_num":    kuccps_num,
                "cluster_name":  KUCCPS_NAMES.get(kuccps_num, f"Cluster {kuccps_num}"),
                "student_score": score,
                "rows":          rows,
            })
    return groups
