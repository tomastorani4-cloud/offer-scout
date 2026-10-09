import unittest
from helpers import rec, settings
from offer_scout.scoring import confidence, decide, score_cluster


def cfg(**attrs):
    base = dict(specific_problem=4, identifiable_audience=5, demonstrable=4, auto_delivery=5, derivatives=5,
                support_load=4, marginal_cost=5, upsell_potential=4, underserved_segment=3,
                specific_application=2, ux_improvable=2, bundle_original=1)
    base.update(attrs)
    return {"attrs": base}


class ScoringTests(unittest.TestCase):
    def test_total_equals_components_minus_penalties_and_is_clamped(self):
        recs = [rec(i) for i in range(12)]
        s = score_cluster(recs, cfg(), settings(), 0, 12, {})
        parts = s.demand + s.persistence + s.quality + s.viability + s.differentiation + sum(p["points"] for p in s.penalties)
        self.assertEqual(s.total, max(0, min(100, parts)))
        self.assertTrue(0 <= s.total <= 100)

    def test_missing_evidence_scores_zero_and_is_reported(self):
        recs = [rec(1, review_count=None, recent_review_count_90d=None, price_usd=None)]
        s = score_cluster(recs, cfg(), settings(), 0, 1, {})
        self.assertEqual(s.demand, 0)
        self.assertTrue(any("No search trend" in l for l in s.limitations))
        self.assertTrue(any("No visible prices" in l for l in s.limitations))

    def test_undated_reviews_are_capped(self):
        recs = [rec(i, recent_review_count_90d=None, review_count=5000) for i in range(3)]
        s = score_cluster(recs, cfg(), settings(), 0, 3, {})
        self.assertTrue(any("undated" in n for n in s.notes))
        self.assertLessEqual(s.demand, 5 + 3)  # reviews capped at 5, sellers up to 3 here

    def test_ad_persistence_tiers(self):
        for days, pts in [(6, 0), (7, 4), (14, 8), (30, 12), (45, 15)]:
            ad = rec(1, signal_type="AD_PERSISTENCE", runtime_days=days, review_count=None, recent_review_count_90d=None, price_usd=None)
            s = score_cluster([ad], cfg(), settings(), 0, 1, {})
            self.assertEqual(s.persistence, pts, f"{days} days")

    def test_persistence_uses_larger_path_not_sum(self):
        ads = [rec(1, signal_type="AD_PERSISTENCE", runtime_days=50, variants=1, review_count=None, recent_review_count_90d=None)]
        mk = [rec(i + 10, recent_review_count_90d=200) for i in range(12)]
        s = score_cluster(ads + mk, cfg(), settings(), 0, 13, {})
        self.assertLessEqual(s.persistence, 20)

    def test_blocked_niche_scores_zero(self):
        s = score_cluster([rec(1)], {"blocked": True, "blocked_reason": "x"}, settings(), 0, 1, {})
        self.assertEqual(s.total, 0)
        self.assertEqual(s.penalties[0]["points"], -100)

    def test_price_floor_and_unproven_claim_penalties(self):
        recs = [rec(i, price_usd=2.0) for i in range(5)]
        s = score_cluster(recs, cfg(), settings(), 0, 5, {"unproven_claim": 3})
        reasons = " ".join(p["reason"] for p in s.penalties)
        self.assertIn("too low", reasons)
        self.assertIn("unproven", reasons)

    def test_confidence_levels(self):
        self.assertEqual(confidence([rec(1)]), "LOW")
        mixed = [rec(1, source_platform="etsy"), rec(2, signal_type="AD_PERSISTENCE", source_platform="meta_ads"),
                 rec(3, signal_type="SEARCH_TREND", source_platform="csv")]
        self.assertEqual(confidence(mixed), "MEDIUM")
        op = rec(4, signal_type="OPERATOR_DATA", reliability="A1")
        self.assertEqual(confidence([op]), "HIGH")

    def test_ad_age_alone_never_gives_high_confidence(self):
        ads = [rec(i, signal_type="AD_PERSISTENCE", runtime_days=200, reliability="B3") for i in range(20)]
        self.assertNotEqual(confidence(ads), "HIGH")

    def test_simulated_never_exceeds_low(self):
        recs = [rec(1, simulated=True, signal_type="OPERATOR_DATA", reliability="A1")]
        self.assertEqual(confidence(recs), "LOW")

    def test_decision_rules(self):
        self.assertEqual(decide(90, "LOW", False, False)[0], "VALIDATE")      # capped
        self.assertEqual(decide(90, "MEDIUM", False, False)[0], "PRIORITY")
        self.assertEqual(decide(70, "LOW", False, False)[0], "VALIDATE")
        self.assertEqual(decide(50, "LOW", False, False)[0], "WATCH")
        self.assertEqual(decide(39, "LOW", False, False)[0], "REJECT")
        self.assertEqual(decide(95, "HIGH", True, False)[0], "REJECT")


if __name__ == "__main__":
    unittest.main()
