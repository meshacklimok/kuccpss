"""
Cutoff prediction engine.

Reads CourseOffering.cutoff_points JSON, e.g. {"2023": 34.2, "2024": 33.8, "2025": 35.1}
(keys are KCSE exam years exactly as labelled on the KUCCPS portal) and produces a
forward estimate for the year after the newest key using TWO methods.

CLUSTER NUMBERING
-----------------
KUCCPS has 18 clusters numbered 1–18. The DB stores them as Cluster rows 101–118
(KUCCPS number = calc number − 100); these carry the calculator SubjectGroups and
degree courses link to them directly (there are no sub-clusters any more).
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

# ── KUCCPS canonical cluster names (1–18) ─────────────────────────────────────

from clusters.constants import CALC_CLUSTER_OFFSET, KUCCPS_CLUSTER_NAMES as KUCCPS_NAMES  # noqa: E402


# Calculator cluster (101–118) → KUCCPS cluster (1–18): simply subtract 100
def calc_to_kuccps(calc_num: int) -> int:
    return calc_num - CALC_CLUSTER_OFFSET


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
    Predict next year's cutoff (newest KCSE year + 1) from historical data.

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
    calc_cluster_number: 101–118
    Fetches all CourseOfferings for that KUCCPS cluster and returns
    enriched rows sorted by eligibility rank then predicted cutoff.
    """
    from courses.models import CourseOffering

    offerings = (
        CourseOffering.objects
        .filter(course__cluster__number=calc_cluster_number)
        .select_related("course", "institution__institution_type", "course__cluster",
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
    cluster_scores: {calc_cluster_number (101–118): student_score}
    Returns grouped results per KUCCPS cluster (1–18), only clusters with matches.
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
