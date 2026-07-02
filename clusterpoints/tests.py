from django.test import TestCase
from django.urls import reverse

from clusterpoints.services import _weighted_cp, GRADE_MIDPOINT_MARKS, compute_aggregate_total


class ClusterPointsFormulaTests(TestCase):
    """Guard the weighted formula: 48 × sqrt((core_marks/400) × (agg/84)), capped at 48."""

    def test_all_A_grades_near_46(self):
        # 4×A (grade 12, midpoint 90.2) → core_marks=360.8, agg=84
        # expected ≈ 48×sqrt(0.902) ≈ 45.59
        from math import sqrt
        core_marks = 4 * GRADE_MIDPOINT_MARKS[12]
        expected = round(48 * sqrt((core_marks / 400) * (84 / 84)), 3)
        result = _weighted_cp([12, 12, 12, 12], 84)
        self.assertAlmostEqual(result, expected, places=2)

    def test_known_calculation(self):
        from math import sqrt
        core_pts = [10, 9, 8, 7]
        agg = 60
        core_marks = sum(GRADE_MIDPOINT_MARKS[p] for p in core_pts)
        expected = round(min(48 * sqrt((core_marks / 400) * (agg / 84)), 48.0), 3)
        result = _weighted_cp(core_pts, agg)
        self.assertAlmostEqual(result, expected, places=3)

    def test_zero_aggregate_gives_zero(self):
        result = _weighted_cp([12, 12, 12, 12], 0)
        self.assertEqual(result, 0.0)

    def test_result_never_exceeds_48(self):
        result = _weighted_cp([12, 12, 12, 12], 84)
        self.assertLessEqual(result, 48.0)

    def test_only_first_four_core_subjects_used(self):
        with_extra = _weighted_cp([12, 12, 12, 12, 1, 1], 84)
        without_extra = _weighted_cp([12, 12, 12, 12], 84)
        self.assertAlmostEqual(with_extra, without_extra, places=3)

    def test_lower_grades_give_lower_points(self):
        high = _weighted_cp([12, 12, 12, 12], 84)
        low = _weighted_cp([6, 6, 6, 6], 48)
        self.assertGreater(high, low)


class AggregateTotalTests(TestCase):
    """
    Guard CLAUDE.md rule #2: aggregate (max 84) = Mathematics + best(English,
    Kiswahili) + next 5 best subjects. The non-best language returns to the
    pool (not discarded) before picking the top 5.
    """

    def test_math_plus_best_language_plus_five_best(self):
        points = {
            'Mathematics': 12,   # always included
            'English': 10,
            'Kiswahili': 6,      # loses to English, returns to pool
            'Biology': 11,
            'Chemistry': 9,
            'Physics': 8,
            'History': 7,
            'Geography': 5,
            'CRE': 4,            # excluded — 8th-best, only top 5 "next" subjects count
        }
        # Mathematics(12) + English(10) + best 5 of remaining pool
        # {Kiswahili:6, Biology:11, Chemistry:9, Physics:8, History:7, Geography:5, CRE:4}
        # top 5 = 11+9+8+7+6 = 41
        expected = 12 + 10 + (11 + 9 + 8 + 7 + 6)
        self.assertEqual(compute_aggregate_total(points), expected)

    def test_non_best_language_returns_to_pool(self):
        # Kiswahili loses to English but is strong enough to place in top 5 anyway.
        points = {
            'Mathematics': 12,
            'English': 10,
            'Kiswahili': 9,
            'Biology': 3,
            'Chemistry': 2,
            'Physics': 1,
        }
        # Math(12) + English(10) + top5 of {Kiswahili:9, Biology:3, Chemistry:2, Physics:1}
        # = 9+3+2+1 = 15 (only 4 available)
        expected = 12 + 10 + (9 + 3 + 2 + 1)
        self.assertEqual(compute_aggregate_total(points), expected)

    def test_missing_mathematics_does_not_crash(self):
        points = {'English': 10, 'Kiswahili': 8, 'Biology': 9, 'Chemistry': 7,
                  'Physics': 6, 'History': 5, 'Geography': 4}
        # No Mathematics → English(10, best language) + top5 of {Kiswahili:8, Biology:9,
        # Chemistry:7, Physics:6, History:5, Geography:4} = 9+8+7+6+5 = 35
        expected = 10 + (9 + 8 + 7 + 6 + 5)
        self.assertEqual(compute_aggregate_total(points), expected)

    def test_missing_both_languages(self):
        points = {'Mathematics': 12, 'Biology': 11, 'Chemistry': 10,
                  'Physics': 9, 'History': 8, 'Geography': 7}
        expected = 12 + (11 + 10 + 9 + 8 + 7)
        self.assertEqual(compute_aggregate_total(points), expected)

    def test_max_possible_aggregate_is_84(self):
        points = {
            'Mathematics': 12, 'English': 12, 'Kiswahili': 12,
            'Biology': 12, 'Chemistry': 12, 'Physics': 12, 'History': 12, 'Geography': 12,
        }
        self.assertEqual(compute_aggregate_total(points), 84)


class ClusterCalculatorViewTests(TestCase):
    def test_calculator_page_loads(self):
        response = self.client.get(reverse('clusterpoints:calculator'))
        self.assertIn(response.status_code, [200, 301, 302])
