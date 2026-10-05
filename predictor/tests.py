from unittest import mock

from django.test import TestCase

from predictor.services import calc_to_kuccps, compute_floor_stats, eligibility, predict_cutoff
from predictor.models import PredictionConfig


class PredictCutoffTests(TestCase):
    def test_no_history_returns_none(self):
        self.assertIsNone(predict_cutoff(None))
        self.assertIsNone(predict_cutoff({}))

    def test_single_year_uses_latest_as_prediction(self):
        pred = predict_cutoff({"2024": 35.0})
        self.assertEqual(pred["years_used"], 1)
        self.assertEqual(pred["latest_cutoff"], 35.0)

    def test_stable_trend_detected(self):
        pred = predict_cutoff({"2023": 35.0, "2024": 35.1})
        self.assertEqual(pred["trend"], "stable")

    def test_rising_trend_detected(self):
        pred = predict_cutoff({"2023": 33.0, "2024": 35.0})
        self.assertEqual(pred["trend"], "rising")

    def test_falling_trend_detected(self):
        pred = predict_cutoff({"2023": 35.0, "2024": 33.0})
        self.assertEqual(pred["trend"], "falling")

    def test_rising_trend_never_predicts_below_latest(self):
        pred = predict_cutoff({"2021": 30.0, "2022": 31.0, "2023": 32.0, "2024": 35.0})
        self.assertGreaterEqual(pred["predicted"], pred["latest_cutoff"])

    def test_predicted_capped_at_48(self):
        pred = predict_cutoff({"2023": 46.0, "2024": 48.0})
        self.assertLessEqual(pred["predicted"], 48.0)
        self.assertLessEqual(pred["high"], 48.0)

    def test_predicted_never_negative(self):
        pred = predict_cutoff({"2023": 1.0, "2024": 0.2})
        self.assertGreaterEqual(pred["low"], 0.0)

    def test_low_never_exceeds_predicted(self):
        pred = predict_cutoff({"2021": 30.0, "2022": 31.0, "2023": 32.0, "2024": 33.0})
        self.assertLessEqual(pred["low"], pred["predicted"])
        self.assertGreaterEqual(pred["high"], pred["predicted"])


class EligibilityTests(TestCase):
    def setUp(self):
        self.pred = {"predicted": 35.0, "low": 33.0, "high": 37.0}

    def test_high_likelihood_above_band(self):
        self.assertEqual(eligibility(38.0, self.pred)["key"], "HighLikelihood")

    def test_likely_at_predicted(self):
        self.assertEqual(eligibility(35.0, self.pred)["key"], "Likely")

    def test_borderline_within_band(self):
        self.assertEqual(eligibility(33.5, self.pred)["key"], "Borderline")

    def test_unlikely_below_band(self):
        self.assertEqual(eligibility(30.0, self.pred)["key"], "Unlikely")

    def test_rank_ordering_matches_likelihood(self):
        ranks = [
            eligibility(38.0, self.pred)["rank"],
            eligibility(35.0, self.pred)["rank"],
            eligibility(33.5, self.pred)["rank"],
            eligibility(30.0, self.pred)["rank"],
        ]
        self.assertEqual(ranks, sorted(ranks))


class FloorRegimeTests(TestCase):
    """Programmes whose latest cutoff is a shared per-cluster floor (did not fill)."""

    def setUp(self):
        # 10 programmes share floor 15.5 in 2023 and 2024; half of them were once competitive
        histories = []
        for i in range(10):
            h = {"2023": 15.5, "2024": 15.5}
            if i < 5:
                h["2022"] = 30.0 + i
            histories.append((h, False))
        # one programme fills in 2024 after a floor 2023
        histories.append(({"2022": 31.0, "2023": 15.5, "2024": 29.0}, False))
        self.stats = compute_floor_stats(histories)

    def test_shared_value_detected_as_floor(self):
        self.assertIn(15.5, self.stats["floors"]["2024"])
        self.assertNotIn(29.0, self.stats["floors"]["2024"])

    def test_floor_programme_uses_minimum_regime(self):
        pred = predict_cutoff({"2023": 15.5, "2024": 15.5}, False, stats=self.stats)
        self.assertEqual(pred["regime"], "minimum")
        self.assertEqual(pred["floor"], 15.5)
        self.assertLess(pred["p_fill"], 0.5)
        self.assertEqual(pred["predicted"], 15.5)
        self.assertIn("Usually doesn't fill", pred["note"])

    def test_returning_programme_refills_below_last_competitive(self):
        pred = predict_cutoff({"2022": 31.0, "2023": 15.5, "2024": 15.5}, False, stats=self.stats)
        self.assertEqual(pred["if_filled"], 29.5)

    def test_competitive_programme_unchanged(self):
        h = {"2022": 31.0, "2023": 15.5, "2024": 29.0}
        with_stats = predict_cutoff(h, False, stats=self.stats)
        without = predict_cutoff(h, False, stats={"floors": {}, "fill": {}})
        self.assertEqual(with_stats["regime"], "competitive")
        self.assertEqual(with_stats["predicted"], without["predicted"])

    def test_meeting_minimum_is_likely_when_rarely_fills(self):
        pred = predict_cutoff({"2023": 15.5, "2024": 15.5}, False, stats=self.stats)
        self.assertIn(eligibility(16.0, pred)["key"], ("HighLikelihood", "Likely"))
        self.assertEqual(eligibility(12.0, pred)["key"], "Unlikely")
        self.assertGreater(eligibility(30.0, pred)["chance"], eligibility(16.0, pred)["chance"])

    def test_competitive_eligibility_has_chance(self):
        elig = eligibility(35.0, {"predicted": 35.0, "low": 33.0, "high": 37.0})
        self.assertEqual(elig["chance"], 50)


class CohortShiftTests(TestCase):
    def _with_shift(self, shift, *args, **kwargs):
        import predictor.services as ps
        cfg = ps._DefaultConfig()
        cfg.cohort_shift = shift
        with mock.patch.object(ps, "_get_config", return_value=cfg):
            return predict_cutoff(*args, **kwargs)

    def test_zero_shift_changes_nothing(self):
        h = {"2023": 33.0, "2024": 35.0}
        self.assertEqual(self._with_shift(0.0, h), self._with_shift(0.0, h))
        self.assertNotIn("cohort_shift", self._with_shift(0.0, h))

    def test_shift_moves_competitive_prediction_and_band(self):
        h = {"2023": 33.0, "2024": 35.0}
        base, up = self._with_shift(0.0, h), self._with_shift(1.0, h)
        for key in ("predicted", "low", "high"):
            self.assertAlmostEqual(up[key], base[key] + 1.0, places=2)
        self.assertEqual(up["latest_cutoff"], base["latest_cutoff"])

    def test_shift_moves_floor_programmes(self):
        stats = compute_floor_stats([({"2023": 15.5, "2024": 15.5}, False) for _ in range(10)])
        base = self._with_shift(0.0, {"2023": 15.5, "2024": 15.5}, False, stats=stats)
        down = self._with_shift(-0.8, {"2023": 15.5, "2024": 15.5}, False, stats=stats)
        self.assertAlmostEqual(down["floor"], base["floor"] - 0.8, places=2)
        self.assertAlmostEqual(down["if_filled"], base["if_filled"] - 0.8, places=2)
        self.assertAlmostEqual(down["predicted"], base["predicted"] - 0.8, places=2)

    def test_shift_stays_within_0_48(self):
        self.assertLessEqual(self._with_shift(2.0, {"2023": 47.5, "2024": 48.0})["high"], 48.0)


class ClusterMappingTests(TestCase):
    def test_calc_to_kuccps_subtracts_100(self):
        self.assertEqual(calc_to_kuccps(113), 13)
        self.assertEqual(calc_to_kuccps(101), 1)
        self.assertEqual(calc_to_kuccps(118), 18)

    def test_eighteen_kuccps_clusters(self):
        from predictor.services import KUCCPS_NAMES
        self.assertEqual(sorted(KUCCPS_NAMES), list(range(1, 19)))


class PredictionConfigTests(TestCase):
    def test_get_creates_singleton_with_defaults(self):
        cfg = PredictionConfig.get()
        self.assertEqual(cfg.pk, 1)
        self.assertEqual(cfg.band_multiplier, 1.5)

    def test_get_is_idempotent(self):
        first = PredictionConfig.get()
        second = PredictionConfig.get()
        self.assertEqual(first.pk, second.pk)

    def test_save_always_forces_pk_1(self):
        cfg = PredictionConfig(pk=99, band_multiplier=2.0)
        cfg.save()
        self.assertEqual(cfg.pk, 1)
        self.assertEqual(PredictionConfig.objects.count(), 1)
