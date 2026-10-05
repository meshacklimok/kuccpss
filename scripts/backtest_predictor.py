"""Backtest predictor.services against real portal history: predict year T from years < T.

    python manage.py shell -c "exec(open('scripts/backtest_predictor.py').read())"

Compares the production model (floor-aware) with the same model with floor detection
off (= pre-Oct-2026 behaviour). Truth for a programme with no cutoff in year T after a
cutoff in T-1: from KCSE 2025 the portal blanks programmes that did not fill, so it is
scored as "admitted if score >= the minimum". That year's minimum isn't published, so we
use the programme's own minimum last year; a programme that was competitive last year
has no own minimum, so it gets the cluster's lowest floor last year. (Using the cluster's
lowest floor for every blank scores 41% of 2025 blanks more than 2 points below their own
minimum, because several DB clusters hold more than one floor; see MLLabz L-001.)
Before 2025 a blank means not offered and is skipped. Students are simulated at last year's value
−2..+8 in 0.5 steps.
"""
import statistics as st
from collections import defaultdict

from courses.models import CourseOffering
from predictor.services import admission_chance, compute_floor_stats, eligibility, predict_cutoff

OFF = {"floors": {}, "fill": {}}
data = [
    ({str(y): float(v) for y, v in o.cutoff_points.items() if v is not None},
     o.institution.institution_type.slug == "private-university", o.course.cluster_id)
    for o in CourseOffering.objects.filter(course__course_type__name="Degree")
    .exclude(cutoff_points__isnull=True).select_related("institution__institution_type", "course")
]
newest = max(int(y) for h, _, _ in data for y in h)


def q(v, x):
    return sorted(v)[int(x * (len(v) - 1))]


for T in range(newest - 2, newest + 1):   # 2023, 2024, 2025
    P, TY = str(T - 1), str(T)
    stats = compute_floor_stats([({y: v for y, v in h.items() if int(y) < T}, pv) for h, pv, _ in data])
    clus_floor = defaultdict(lambda: 99.0)
    for h, _, c in data:
        if P in h and round(h[P], 3) in stats["floors"].get(P, ()):
            clus_floor[c] = min(clus_floor[c], h[P])

    err, dec, brier = defaultdict(list), defaultdict(list), defaultdict(list)
    for h, pv, c in data:
        if P not in h:
            continue
        if TY in h:
            actual = h[TY]
        elif T >= 2025 and round(h[P], 3) in stats["floors"].get(P, ()):
            actual = h[P]                      # own minimum last year
        elif T >= 2025 and clus_floor[c] < 99:
            actual = clus_floor[c]
        else:
            continue
        past = {y: v for y, v in h.items() if int(y) < T}
        for name, s in (("old", OFF), ("new", stats)):
            pred = predict_cutoff(past, pv, stats=s)
            err[name].append(abs(pred["predicted"] - actual))
            for d in range(-4, 17):
                score = past[P] + d * 0.5
                admitted = score >= actual - 1e-9
                told_yes = eligibility(score, pred)["rank"] <= 2
                dec[name].append((told_yes, admitted))
                brier[name].append((admission_chance(score, pred) - admitted) ** 2)

    print(f"\n=== Predict {T} from years before it ({len(err['old'])} programmes) ===")
    for name in ("old", "new"):
        e, d = err[name], dec[name]
        print(f"  {name}: median miss {q(e, .5):.2f}  avg {st.mean(e):.2f}  80% within {q(e, .8):.2f}  | "
              f"right call {sum(a == b for a, b in d) / len(d):.1%}  "
              f"told likely but rejected {sum(a and not b for a, b in d) / len(d):.1%}  "
              f"told unlikely but admitted {sum(b and not a for a, b in d) / len(d):.1%}  "
              f"Brier {st.mean(brier[name]):.3f}")
