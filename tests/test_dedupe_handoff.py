import unittest
from helpers import rec
from offer_scout.dedupe import dedupe, saturation_share
from offer_scout.handoff import VerbatimLeak, assert_no_verbatim


class DedupeTests(unittest.TestCase):
    def test_same_seller_near_identical_titles_merge_with_variants(self):
        a = rec(1, seller="s", product_name="Pet Sitter Business Template Spreadsheet", runtime_days=10, signal_type="AD_PERSISTENCE")
        b = rec(2, seller="s", product_name="Pet Sitter Business Template Spreadsheet!", runtime_days=40, signal_type="AD_PERSISTENCE")
        out = dedupe([a, b])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].variants, 2)
        self.assertEqual(out[0].runtime_days, 40)

    def test_different_sellers_do_not_merge(self):
        a = rec(1, seller="s1", product_name="Pet Sitter Template")
        b = rec(2, seller="s2", product_name="Pet Sitter Template")
        self.assertEqual(len(dedupe([a, b])), 2)

    def test_saturation_detects_clones_across_sellers(self):
        clones = [rec(i, seller=f"s{i}", product_name="Pet Health Record Printable Vaccination Log") for i in range(6)]
        self.assertGreaterEqual(saturation_share(clones, 0.7), 0.99)
        distinct = [rec(i, seller=f"s{i}", product_name=f"Totally different words {i} zebra{i} quartz{i}") for i in range(6)]
        self.assertEqual(saturation_share(distinct, 0.7), 0.0)


class HandoffTests(unittest.TestCase):
    def test_verbatim_competitor_title_is_blocked(self):
        recs = [rec(1, product_name="Paws & Profits Pet Sitting Business Manager")]
        with self.assertRaises(VerbatimLeak):
            assert_no_verbatim({"note": "inspired by Paws & Profits Pet Sitting Business Manager"}, recs)

    def test_abstractions_pass(self):
        recs = [rec(1, product_name="Paws & Profits Pet Sitting Business Manager")]
        assert_no_verbatim({"core_problem": "organizing a pet sitting business"}, recs)


if __name__ == "__main__":
    unittest.main()
