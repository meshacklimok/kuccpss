from django.test import TestCase
from django.urls import reverse

from clusterpoints.services import _weighted_cp, GRADE_MIDPOINT_MARKS


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


class ClusterCalculatorViewTests(TestCase):
    def test_calculator_page_loads(self):
        response = self.client.get(reverse('clusterpoints:calculator'))
        self.assertIn(response.status_code, [200, 301, 302])
