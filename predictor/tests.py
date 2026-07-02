from django.test import TestCase

from predictor.services import calc_to_kuccps, eligibility, predict_cutoff
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


class ClusterMappingTests(TestCase):
    def test_calc_to_kuccps_subtracts_100(self):
        self.assertEqual(calc_to_kuccps(113), 13)
        self.assertEqual(calc_to_kuccps(101), 1)


class PredictionConfigTests(TestCase):
    def test_get_creates_singleton_with_defaults(self):
        cfg = PredictionConfig.get()
        self.assertEqual(cfg.pk, 1)
        self.assertEqual(cfg.band_multiplier, 1.0)

    def test_get_is_idempotent(self):
        first = PredictionConfig.get()
        second = PredictionConfig.get()
        self.assertEqual(first.pk, second.pk)

    def test_save_always_forces_pk_1(self):
        cfg = PredictionConfig(pk=99, band_multiplier=2.0)
        cfg.save()
        self.assertEqual(cfg.pk, 1)
        self.assertEqual(PredictionConfig.objects.count(), 1)
