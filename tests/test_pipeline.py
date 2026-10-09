import copy
import csv
import tempfile
import unittest
from pathlib import Path

from helpers import NOW, settings
from offer_scout.collectors import CsvImportCollector, EtsyApiCollector, MetaAdLibraryCollector, ParseContext, SyntheticCollector
from offer_scout.config import ConfigError, load_settings
from offer_scout.models import RawRecord
from offer_scout.pipeline import run_pipeline
from offer_scout.report import validate_report
from offer_scout.store import Store


class SimulatedRunTests(unittest.TestCase):
    def setUp(self):
        self.s = settings()
        self.store = Store(":memory:")
        self.col = SyntheticCollector(self.s.subcategories(), seed=7)
        self.report = run_pipeline(self.s, [self.col], self.store, now=NOW)

    def test_report_valid_and_marked_simulated(self):
        self.assertEqual(validate_report(self.report), [])
        self.assertEqual(self.report["run"]["data_mode"], "SIMULATED")

    def test_no_handoff_or_recommendation_from_simulated_data(self):
        self.assertTrue(all(not o["handoff_to_modeler"] for o in self.report["opportunities"]))
        self.assertIsNone(self.report["recommended_next_action"]["selected_opportunity_id"])
        self.assertEqual(self.store.pending_events("modeler", "scout.opportunity.ready_for_modeling"), [])

    def test_autism_nutrition_niche_is_rejected_with_reason(self):
        o = next(o for o in self.report["opportunities"] if o["subcategory"] == "autism_nutrition_intervention")
        self.assertEqual(o["decision"], "REJECT")
        self.assertEqual(o["score"]["total"], 0)
        self.assertIn("Blocked", o["decision_reason"])

    def test_condition_specific_caregiver_listings_are_excluded(self):
        o = next(o for o in self.report["opportunities"] if o["subcategory"] == "caregiver_handover")
        self.assertGreaterEqual(o["compliance"]["records_rejected"], 2)

    def test_events_and_consumption(self):
        evs = self.store.pending_events("dashboard", "scout.run.completed")
        self.assertEqual(len(evs), 1)
        self.store.mark_consumed(evs[0]["id"], "dashboard")
        self.assertEqual(self.store.pending_events("dashboard", "scout.run.completed"), [])
        self.assertEqual(len(self.store.pending_events("modeler", "scout.run.completed")), 1)

    def test_deterministic(self):
        again = run_pipeline(self.s, [SyntheticCollector(self.s.subcategories(), seed=7)], Store(":memory:"), now=NOW)
        a = {o["subcategory"]: o["score"]["total"] for o in self.report["opportunities"]}
        b = {o["subcategory"]: o["score"]["total"] for o in again["opportunities"]}
        self.assertEqual(a, b)


class OperatorDataRunTests(unittest.TestCase):
    """LIVE-mode path using an operator CSV: handoff allowed, HIGH confidence only with operator data."""

    def test_operator_csv_enables_handoff(self):
        s = settings()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "ops.csv"
            with open(path, "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["source_platform", "source_id", "signal_type", "seller", "product_name", "text", "price", "currency",
                            "review_count", "recent_review_count_90d", "sales_count_visible", "data_class", "source_url"])
                for i in range(14):
                    w.writerow(["shop_export", f"o{i}", "OPERATOR_DATA", f"shop{i}", f"Kit variant {i} alpha{i} beta{i}",
                                "pet sitter business template spreadsheet instant download", "24", "USD", "300", "90", "400", "operator",
                                f"https://ops.test/{i}"])
            store = Store(":memory:")
            report = run_pipeline(s, [CsvImportCollector([str(path)])], store, now=NOW)
        self.assertEqual(validate_report(report), [])
        self.assertEqual(report["run"]["data_mode"], "LIVE")
        o = next(o for o in report["opportunities"] if o["subcategory"] == "pet_business_kit")
        self.assertEqual(o["evidence_confidence"], "HIGH")
        self.assertTrue(o["handoff_to_modeler"])
        events = store.pending_events("modeler", "scout.opportunity.ready_for_modeling")
        self.assertEqual(len(events), 1)
        payload = events[0]["payload"]
        self.assertNotIn("Kit variant", str(payload))
        self.assertTrue(payload["human_approval_required"])


class AdapterParseTests(unittest.TestCase):
    ctx = ParseContext(fx={"USD": 1.0, "GBP": 1.27}, now=NOW, lookback_days=90)

    def test_meta_ad_parse_runtime_and_active(self):
        col = MetaAdLibraryCollector(token="x", http=object())
        raw = RawRecord("meta_ads", "1", "https://snap", "2026-10-06T00:00:00Z", "q", "GB",
                        {"id": "1", "page_name": "Acme", "ad_delivery_start_time": "2026-08-01",
                         "ad_creative_bodies": ["Start your dog walking business"], "ad_creative_link_titles": ["Dog walker kit"]})
        rec = col.parse(raw, self.ctx)
        self.assertEqual(rec.signal_type, "AD_PERSISTENCE")
        self.assertEqual(rec.runtime_days, 66)
        self.assertTrue(rec.active)

    def test_meta_warns_about_us_coverage(self):
        col = MetaAdLibraryCollector(token="x", http=object())
        self.assertTrue(col.coverage_warnings("US"))
        self.assertFalse(col.coverage_warnings("GB"))

    def test_etsy_parse_price_and_recent_reviews(self):
        col = EtsyApiCollector(api_key="k", http=object())
        raw = RawRecord("etsy", "9", "https://etsy/9", "2026-10-06T00:00:00Z", "q", "US", {
            "listing_id": 9, "title": "Pet Sitter Template", "shop_id": 5, "type": "download",
            "price": {"amount": 1999, "divisor": 100, "currency_code": "USD"}, "num_favorers": 3, "tags": ["pet sitter"],
            "_reviews": {"count": 40, "timestamps": [1790000000, 1700000000]}})
        rec = col.parse(raw, self.ctx)
        self.assertEqual(rec.price_usd, 19.99)
        self.assertEqual(rec.review_count, 40)
        self.assertEqual(rec.recent_review_count_90d, 1)
        self.assertEqual(rec.signal_type, "REVIEW_VELOCITY")

    def test_etsy_skips_physical(self):
        col = EtsyApiCollector(api_key="k", http=object())
        raw = RawRecord("etsy", "9", None, "2026-10-06T00:00:00Z", "q", "US", {"listing_id": 9, "type": "physical"})
        self.assertIsNone(col.parse(raw, self.ctx))

    def test_unknown_currency_is_not_guessed(self):
        col = EtsyApiCollector(api_key="k", http=object())
        raw = RawRecord("etsy", "9", None, "2026-10-06T00:00:00Z", "q", "US", {
            "listing_id": 9, "title": "x", "type": "download", "price": {"amount": 500, "divisor": 100, "currency_code": "XYZ"}})
        self.assertIsNone(col.parse(raw, self.ctx).price_usd)


class GovernanceTests(unittest.TestCase):
    def test_auto_publish_is_refused(self):
        s = settings()
        with tempfile.TemporaryDirectory() as d:
            import shutil, yaml
            shutil.copytree(s.root / "config", Path(d) / "config")
            cfg = yaml.safe_load(open(Path(d) / "config/settings.yaml"))
            cfg["governance"]["auto_publish"] = True
            yaml.safe_dump(cfg, open(Path(d) / "config/settings.yaml", "w"))
            with self.assertRaises(ConfigError):
                load_settings(Path(d) / "config")


if __name__ == "__main__":
    unittest.main()


class DashboardExportTests(unittest.TestCase):
    def test_export_writes_latest_history_status_and_dedupes_history(self):
        import json
        from offer_scout.dashboard_export import export_run, write_status
        s = settings()
        report = run_pipeline(s, [SyntheticCollector(s.subcategories(), seed=7)], Store(":memory:"), now=NOW)
        with tempfile.TemporaryDirectory() as d:
            export_run(report, d)
            export_run(report, d)  # same run twice must not duplicate history
            hist = json.loads((Path(d) / "history.json").read_text())
            self.assertEqual(len(hist), 1)
            self.assertEqual(json.loads((Path(d) / "latest.json").read_text())["run"]["run_id"], report["run"]["run_id"])
            self.assertEqual(json.loads((Path(d) / "status.json").read_text())["state"], "ok")
            write_status(d, "no_sources", "x", "2026-10-09T00:00:00Z")
            self.assertEqual(json.loads((Path(d) / "status.json").read_text())["state"], "no_sources")

    def test_auto_without_credentials_returns_no_collectors(self):
        import os
        from offer_scout.pipeline import build_collectors
        s = settings()
        old = {k: os.environ.pop(k, None) for k in ("ETSY_API_KEY", "META_AD_LIBRARY_TOKEN")}
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                self.assertEqual(build_collectors(s, simulate=False, auto=True), [])
            finally:
                os.chdir(cwd)
                for k, v in old.items():
                    if v: os.environ[k] = v
