"""
Cutoff prediction engine.

Reads CourseOffering.cutoff_points JSON, e.g. {"2023": 34.2, "2024": 33.8, "2025": 35.1}
(keys are KCSE exam years exactly as labelled on the KUCCPS portal) and produces a
forward estimate for the year after the newest key.

TWO REGIMES
-----------
About 57% of degree programmes do not fill in a given year. For those the portal
printed a per-cluster minimum ("floor") that hundreds of programmes share in the same
year (e.g. 15.092 × 220 in 2024); from KCSE 2025 it leaves them blank instead.
  * Competitive last year  -> blended trend model (predict_cutoff below).
  * Floor last year        -> hurdle model: P(fills) from history, and the cutoff if
                              it does (see _hurdle). Anyone meeting the minimum gets in
                              when it doesn't fill.

CLUSTER NUMBERING
-----------------
KUCCPS has 18 clusters numbered 1–18. The DB stores them as Cluster rows 101–118
(KUCCPS number = calc number − 100); these carry the calculator SubjectGroups and
degree courses link to them directly (there are no sub-clusters any more).
"""

from __future__ import annotations
import math
import time as _time
from collections import Counter, defaultdict

# ── DB config cache (refreshed every 60 s) ────────────────────────────────────

class _DefaultConfig:
    rising_floor_multiplier = 0.0
    rising_floor_cap        = 3.0
    stable_floor_offset     = 0.0
    band_multiplier         = 1.5
    cohort_shift            = 0.0

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


# ── Floor detection + fill rates (refreshed hourly) ──────────────────────────
#
# Backtest, Oct 2026 (fill rates learned from earlier years only; P(fill) given a
# floor last year):          2023   2024   2025
#   never competitive, private   2%     1%     2%
#   never competitive, public    8%     5%    15%
#   competitive before, public  59%    50%    49%
# scripts/backtest_predictor.py, floor detection off -> on (2025 blanks scored against
# their own 2024 minimum): right likely/unlikely call 87.0 -> 88.8% (2023),
# 86.2 -> 87.9% (2024), 84.5 -> 87.8% (2025); Brier 0.100 -> 0.090, 0.104 -> 0.088,
# 0.113 -> 0.100.
#
# FILLED_SD 1.5 -> 2.5 (MLLabz L-005): when a floor programme filled, the real cutoff was
# within ±1.5 of if_filled only 31-47% of the time (1.5 assumes 68%); misses had a spread
# of 2.5-3.4. Brier on floor programmes 0.0720 -> 0.0713 (2023), 0.0722 -> 0.0705 (2024),
# 0.0857 -> 0.0856 (2025); labels barely move. A cluster-median cutoff for first-time
# fillers guessed if_filled closer but worsened Brier in 2023-24, so "+3" stays.

FLOOR_MIN_SHARED  = 10     # a value printed for >= this many programmes in one year is a floor
FILLED_BELOW_LAST = 1.5    # a returning programme refills ~1.5 below its last competitive cutoff
FILLED_ABOVE_FLOOR = 3.0   # a first-time filler lands ~3 above the floor
FLOOR_DRIFT       = 1.0    # floors move ~±1 a year; being this far below last year's still counts
FILLED_SD         = 2.5    # spread of the competitive cutoff once a programme fills

_floor_cache: dict | None = None
_floor_ts: float = 0.0


def compute_floor_stats(histories: list[tuple[dict, bool | None]]) -> dict:
    """
    histories: [(cutoff_points, is_private), ...] for degree offerings.
    Returns {"floors": {year: {value, ...}}, "fill": {(ever_competitive, sector): rate}}.
    Pure function so backtests can feed it truncated history.
    """
    counts: dict[str, Counter] = defaultdict(Counter)
    for h, _ in histories:
        for y, v in (h or {}).items():
            if v is not None:
                counts[str(y)][round(float(v), 3)] += 1
    floors = {y: {v for v, n in c.items() if n >= FLOOR_MIN_SHARED} for y, c in counts.items()}

    # P(fills next year | floor this year), by whether it was ever competitive before
    tally: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
    years = sorted(floors)
    for h, private in histories:
        h = {str(y): float(v) for y, v in (h or {}).items() if v is not None}
        for prev, nxt in zip(years, years[1:]):
            if prev not in h or round(h[prev], 3) not in floors[prev]:
                continue
            # A blank next year counts as "did not fill" (from KCSE 2025 the portal blanks floors)
            ever = any(round(v, 3) not in floors[y] for y, v in h.items() if y < nxt)
            filled = nxt in h and round(h[nxt], 3) not in floors[nxt]
            for sector in (("private" if private else "public") if private is not None else None, "any"):
                if sector:
                    t = tally[(ever, sector)]
                    t[0] += 1
                    t[1] += filled
    fill = {k: (b + 1) / (a + 2) for k, (a, b) in tally.items()}   # Laplace-smoothed
    return {"floors": floors, "fill": fill}


def _get_floor_stats() -> dict:
    global _floor_cache, _floor_ts
    now = _time.monotonic()
    if _floor_cache is None or now - _floor_ts > 3600:
        try:
            from courses.models import CourseOffering
            qs = (CourseOffering.objects.filter(course__course_type__name="Degree")
                  .exclude(cutoff_points__isnull=True)
                  .values_list("cutoff_points", "institution__institution_type__slug"))
            _floor_cache = compute_floor_stats([(cp, slug == "private-university") for cp, slug in qs])
        except Exception:
            _floor_cache = {"floors": {}, "fill": {}}
        _floor_ts = now
    return _floor_cache


def _phi(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _hurdle(history: dict, is_private: bool | None, stats: dict) -> dict | None:
    """Two-part prediction for a programme whose latest cutoff is a floor; None if it isn't."""
    floors = stats["floors"]
    years  = sorted(history)
    last_y = years[-1]
    floor  = float(history[last_y])
    if round(floor, 3) not in floors.get(last_y, ()):
        return None
    comp = [(y, float(history[y])) for y in years if round(float(history[y]), 3) not in floors.get(y, ())]
    sector = "any" if is_private is None else ("private" if is_private else "public")
    p_fill = stats["fill"].get((bool(comp), sector), stats["fill"].get((bool(comp), "any"), 0.1))
    if comp:
        if_filled = comp[-1][1] - FILLED_BELOW_LAST
    else:
        if_filled = floor + FILLED_ABOVE_FLOOR
    if_filled = max(if_filled, floor + 0.5)
    floor_years = len(years) - len(comp)
    return {
        "p_fill":      round(p_fill, 2),
        "floor":       round(floor, 2),
        "if_filled":   round(min(if_filled, 48.0), 2),
        "floor_years": floor_years,
        "note": (f"Usually doesn't fill — meeting the minimum was enough in {floor_years} of "
                 f"{len(years)} years. About {round(p_fill * 100)}% chance it fills"
                 f" (cutoff then ~{round(if_filled, 1)})."),
    }

# ── KUCCPS canonical cluster names (1–18) ─────────────────────────────────────

from clusters.constants import CALC_CLUSTER_OFFSET, KUCCPS_CLUSTER_NAMES as KUCCPS_NAMES  # noqa: E402


# Calculator cluster (101–118) → KUCCPS cluster (1–18): simply subtract 100
def calc_to_kuccps(calc_num: int) -> int:
    return calc_num - CALC_CLUSTER_OFFSET


# Trend display helpers. The arrow describes last year's move, not a forecast: in the
# Oct 2026 backtest the latest direction repeated only 33-42% of the time (MLLabz L-001).
TREND_LABEL = {"rising": "Rose last year", "stable": "Steady last year", "falling": "Fell last year"}
TREND_ICON  = {"rising": "fa-arrow-trend-up",   "stable": "fa-minus", "falling": "fa-arrow-trend-down"}
TREND_COLOR = {"rising": "text-danger",           "stable": "text-muted","falling": "text-success"}
TREND_TIP   = {
    "rising":  "Rose at the last intake. Past moves don't predict the next one.",
    "stable":  "Moved less than 0.3 points at the last intake.",
    "falling": "Fell at the last intake. Past moves don't predict the next one.",
}


# ── Core prediction ────────────────────────────────────────────────────────────

def predict_cutoff(history: dict | None, is_private: bool | None = None,
                   stats: dict | None = None) -> dict | None:
    """
    Predict next year's cutoff (newest KCSE year + 1) from historical data.

    METHOD: 70% WMA + 30% Naive (latest year), floored at the latest cutoff for
    rising/stable courses.

    Backtest (Oct 2026, MLLabz L-001 v0.3; each year predicted from the years before
    it). Typical miss (median |error|, cluster points), programmes above the minimum
    in both years:
                                 2023    2024    2025
      This model (live)          1.18    1.06    1.18
      Blend, no floors           1.20    1.07    1.33
      Average of earlier years   1.25    1.16    1.45
      Naive (latest)             1.35    1.13    1.36
      Straight-line trend        2.93    1.58    1.49
    The lead over naive is small; most remaining error is a year-wide shift (median
    change 2023 −0.42, 2024 −0.15, 2025 +0.55 above the minimum) that no per-course
    smoother can see. With band_multiplier 1.5 the ± band holds 61–67% of known
    cutoffs (72–78% above the minimum). scripts/backtest_predictor.py re-runs the
    headline numbers.

    WMA weights (recency-weighted):
      2 years: 60/40
      3 years: 50/30/20
      4 years: 40/30/20/10

    Blend applies: prediction = 0.70 × WMA + 0.30 × latest_year_value
    Effective weights (4yr): 58% most recent / 21% / 14% / 7% oldest

    If the latest cutoff is a floor (programme did not fill), the result has
    regime="minimum" plus p_fill / floor / if_filled / note from _hurdle().
    is_private sharpens the fill rate; stats overrides the DB floor stats (backtests).

    COHORT SHIFT: cfg.cohort_shift (admin, default 0) is added to every output
    level — predicted/low/high and, for floor programmes, floor/if_filled. It covers
    the year-wide move no per-course model can see. Set to each year's true median
    change, the typical miss above the minimum drops 1.18 -> 1.13 (2023), 1.06 -> 1.01
    (2024) and 1.18 -> 1.06 (2025); that is a best case, since it uses the answer.
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
    # cutoff, lift the prediction to at least: latest + multiplier × last gain
    # (default multiplier 0.0, i.e. hold at the latest cutoff — best in backtest).
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

    result = {
        "predicted":     predicted,
        "low":           low,
        "high":          high,
        "trend":         trend,
        "years_used":    n,
        "latest_year":   years[-1],
        "latest_cutoff": round(latest, 2),
        "history":       {y: float(history[y]) for y in years},
        "regime":        "competitive",
    }

    # ── Floor last year: two-part (hurdle) prediction instead ─────────────────
    hurdle = _hurdle({y: values[i] for i, y in enumerate(years)}, is_private,
                     stats if stats is not None else _get_floor_stats())
    if hurdle:
        result.update(hurdle)
        result.update({
            "regime":    "minimum",
            "predicted": hurdle["if_filled"] if hurdle["p_fill"] >= 0.5 else hurdle["floor"],
            "low":       round(max(0.0, hurdle["floor"] - FLOOR_DRIFT), 2),
            "high":      round(min(48.0, hurdle["if_filled"] + FILLED_SD), 2),
            "trend":     "stable",
        })

    # ── Cohort-wide shift (admin-set once the new KCSE results are known) ─────
    shift = float(getattr(cfg, "cohort_shift", 0.0) or 0.0)
    if shift:
        for key in ("predicted", "low", "high", "floor", "if_filled"):
            if key in result:
                result[key] = round(max(0.0, min(48.0, result[key] + shift)), 2)
        result["cohort_shift"] = shift
    return result


# ── Eligibility label ──────────────────────────────────────────────────────────

_LABELS = {
    1: {"label": "High Likelihood", "key": "HighLikelihood", "css": "text-success",
        "accent": "card-accent-green",  "icon": "fa-circle-check",       "rank": 1},
    2: {"label": "Likely",          "key": "Likely",         "css": "text-success",
        "accent": "card-accent-green",  "icon": "fa-circle-check",       "rank": 2},
    3: {"label": "Borderline",      "key": "Borderline",     "css": "text-warning",
        "accent": "card-accent-orange", "icon": "fa-circle-exclamation", "rank": 3},
    4: {"label": "Unlikely",        "key": "Unlikely",       "css": "text-danger",
        "accent": "card-accent-red",    "icon": "fa-circle-xmark",       "rank": 4},
}


def admission_chance(student_score: float, pred: dict) -> float:
    """Estimated probability (0–1) that student_score clears next year's cutoff."""
    if pred.get("regime") == "minimum":
        p = pred["p_fill"]
        meets_min = _phi((student_score - (pred["floor"] - FLOOR_DRIFT / 2)) / (FLOOR_DRIFT / 2))
        beats_fill = _phi((student_score - pred["if_filled"]) / FILLED_SD)
        return (1 - p) * meets_min + p * beats_fill
    # The ± band covers ~60% of outcomes, i.e. about ±0.84 standard deviations
    sd = max(pred["high"] - pred["predicted"], 0.5) / 0.84
    return _phi((student_score - pred["predicted"]) / sd)


def eligibility(student_score: float, pred: dict) -> dict:
    """
    Competitive programmes (band around the predicted cutoff):
      High Likelihood — score >= high (above confidence band)
      Likely          — score >= predicted
      Borderline      — score >= low (within confidence band)
      Unlikely        — score < low
    Floor programmes (regime="minimum"), from admission_chance():
      High Likelihood >= 80%, Likely >= 50%, Borderline >= 20%, else Unlikely.
    Every result carries "chance" (whole percent).
    """
    chance = admission_chance(student_score, pred)
    if pred.get("regime") == "minimum":
        rank = 1 if chance >= 0.8 else 2 if chance >= 0.5 else 3 if chance >= 0.2 else 4
    elif student_score >= pred["high"]:
        rank = 1
    elif student_score >= pred["predicted"]:
        rank = 2
    elif student_score >= pred["low"]:
        rank = 3
    else:
        rank = 4
    return {**_LABELS[rank], "chance": round(chance * 100)}


# ── Bulk helpers ───────────────────────────────────────────────────────────────

def is_private_offering(offering) -> bool | None:
    itype = getattr(offering.institution, "institution_type", None)
    return None if itype is None else itype.slug == "private-university"


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
        pred = predict_cutoff(o.cutoff_points, is_private_offering(o))
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
