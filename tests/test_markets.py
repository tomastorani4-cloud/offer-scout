import unittest

from helpers import NOW, rec, settings
from offer_scout.collectors import SyntheticCollector
from offer_scout.compliance import ComplianceScreen
from offer_scout.markets import build_market_ideas, coverage_by_market
from offer_scout.pipeline import run_pipeline
from offer_scout.report import validate_report
from offer_scout.store import Store

S = settings()
SUB = S.subcategories()["pet_business_kit"]


def many(lang, n_sellers, n_records, **kw):
    return [rec(i + hash(lang) % 1000, seller=f"{lang}-s{i % n_sellers}", language=lang, country_verified=True,
                source_id=f"{lang}{i}", record_id=f"{lang}{i}", **kw) for i in range(n_records)]


class MarketIdeaTests(unittest.TestCase):
    def cov(self, **override):
        base = {"en": 400, "pt": 50, "de": 50, "fr": 50, "es": 50}
        base.update(override)
        return base

    def test_gap_supported_needs_source_thin_target_and_coverage(self):
        recs = many("en", 8, 12) + many("pt", 1, 1)
        ideas = {i["target_market"]: i for i in build_market_ideas("pet_business_kit", SUB, recs, self.cov(), S)}
        self.assertEqual(ideas["pt"]["status"], "GAP_SUPPORTED")
        self.assertIn("caveat", ideas["pt"])
        self.assertTrue(ideas["pt"]["requires_human_review"])

    def test_no_coverage_is_unverified_not_a_gap(self):
        recs = many("en", 8, 12)
        ideas = {i["target_market"]: i for i in build_market_ideas("pet_business_kit", SUB, recs, self.cov(pt=0), S)}
        self.assertEqual(ideas["pt"]["status"], "UNVERIFIED")

    def test_niche_not_searched_in_language_is_unverified(self):
        cfg = dict(S.subcategories()["pet_health_record"])   # has no queries_i18n
        recs = many("en", 8, 12)
        ideas = {i["target_market"]: i for i in build_market_ideas("pet_health_record", cfg, recs, self.cov(), S)}
        self.assertTrue(all(i["status"] == "UNVERIFIED" for i in ideas.values()))
        self.assertIn("no search queries", ideas["de"]["rationale"])

    def test_target_with_some_competition_is_competitive(self):
        recs = many("en", 8, 12) + many("de", 3, 5)
        ideas = {i["target_market"]: i for i in build_market_ideas("pet_business_kit", SUB, recs, self.cov(), S)}
        self.assertEqual(ideas["de"]["status"], "COMPETITIVE")

    def test_proven_markets_are_not_targets_and_no_source_means_no_ideas(self):
        recs = many("en", 8, 12) + many("pt", 6, 10)
        langs = {i["target_market"] for i in build_market_ideas("pet_business_kit", SUB, recs, self.cov(), S)}
        self.assertNotIn("pt", langs)
        self.assertNotIn("en", langs)
        self.assertEqual(build_market_ideas("pet_business_kit", SUB, many("en", 2, 3), self.cov(), S), [])

    def test_blocked_niche_gets_no_ideas(self):
        self.assertEqual(build_market_ideas("x", {"blocked": True}, many("en", 8, 12), self.cov(), S), [])

    def test_simulated_never_medium(self):
        recs = many("en", 8, 12, simulated=True) + [rec(99, signal_type="AD_PERSISTENCE", language="en", simulated=True)]
        ideas = build_market_ideas("pet_business_kit", SUB, recs, self.cov(), S)
        self.assertTrue(all(i["confidence"] == "LOW" for i in ideas))

    def test_price_hypothesis_is_conversion_only(self):
        recs = many("en", 8, 12)
        pt = next(i for i in build_market_ideas("pet_business_kit", SUB, recs, self.cov(), S) if i["target_market"] == "pt")
        self.assertEqual(pt["price_hypothesis"]["currency"], "BRL")
        self.assertIn("validate locally", pt["price_hypothesis"]["note"])

    def test_coverage_counts_per_language(self):
        recs = many("en", 3, 5) + many("pt", 2, 3)
        c = coverage_by_market(recs, S)
        self.assertEqual((c["en"], c["pt"], c["de"]), (5, 3, 0))


class MultilingualComplianceTests(unittest.TestCase):
    def setUp(self):
        self.screen = ComplianceScreen(S.compliance)

    def test_rejects_clinical_and_weight_loss_in_each_language(self):
        for text in ["Planilha para emagrecer rápido", "Dieta sem glúten para autismo cardápio", "Heilung Ratgeber Behandlung",
                     "Plan para adelgazar rápido", "Programme minceur perte de poids", "Tratamento caseiro para cachorro dosagem",
                     "Hund Dosierung Hausmittel Vorlage"]:
            self.assertTrue(self.screen.evaluate(text).hard_reject, text)

    def test_financial_gambling_piracy_rejected_and_routed(self):
        self.assertEqual(self.screen.evaluate("Forex trading signals course").assign_subcategory, "get_rich_financial_claims")
        self.assertEqual(self.screen.evaluate("Apostas esportivas dicas").assign_subcategory, "gambling_adult")
        self.assertEqual(self.screen.evaluate("Cracked keygen pack").assign_subcategory, "piracy_hacking")

    def test_benign_localized_listings_pass(self):
        for text in ["Planilha pet sitter | Download Instantâneo", "Hundesitter Vorlage | Sofort Download",
                     "Modèle pet sitter | Téléchargement immédiat", "Plantilla cuidador de mascotas | Descarga inmediata",
                     "Checklist de mudança imprimível", "Familienplaner Vorlage"]:
            self.assertFalse(self.screen.evaluate(text).hard_reject, text)


class MarketPipelineTests(unittest.TestCase):
    def setUp(self):
        self.report = run_pipeline(S, [SyntheticCollector(S.subcategories(), seed=7)], Store(":memory:"), now=NOW)

    def test_report_valid_with_market_ideas_and_coverage(self):
        self.assertEqual(validate_report(self.report), [])
        self.assertEqual(set(self.report["markets"]["coverage_records_by_market"]), {"en", "pt", "de", "fr", "es"})
        o = next(o for o in self.report["opportunities"] if o["subcategory"] == "pet_business_kit")
        self.assertTrue(any(i["target_market"] == "pt" and i["status"] == "GAP_SUPPORTED" for i in o["market_ideas"]))

    def test_new_blocked_niches_rejected_and_never_get_ideas(self):
        for sub in ("get_rich_financial_claims", "gambling_adult", "piracy_hacking"):
            o = next(o for o in self.report["opportunities"] if o["subcategory"] == sub)
            self.assertEqual((o["decision"], o["score"]["total"]), ("REJECT", 0))
            self.assertEqual(o["market_ideas"], [])

    def test_unsupported_language_fails_closed(self):
        from offer_scout.collectors import Collector
        from offer_scout.models import RawRecord, Record

        class OneItalian(Collector):
            name, source_class, country_scoped = "stub", "official_api", True

            def collect(self, query, country, limit):
                return [RawRecord("stub", "it-1", None, "2026-10-09T00:00:00Z", query, country, {}, False)]

            def parse(self, raw, ctx):
                return Record(record_id="it-1", source_platform="stub", source_id="it-1", source_url=None, signal_type="REVIEW_VELOCITY",
                              captured_at=raw.captured_at, seller="x", product_name="Modello pet sitter", text="modello pet sitter",
                              country="IT", reliability="B3")

        s2 = settings()
        s2.markets["it"] = {"label": "Italia", "region": "EUROPE", "countries": ["IT"], "currency": "EUR"}
        s2.localization["subcategories"]["pet_business_kit"]["queries_i18n"]["it"] = ["modello pet sitter"]
        s2.raw["run"]["countries"] = ["IT"]
        rep = run_pipeline(s2, [OneItalian()], Store(":memory:"), now=NOW)
        self.assertEqual(rep["run"]["rejection_reasons"].get("compliance_language_unsupported"), 1)


if __name__ == "__main__":
    unittest.main()
