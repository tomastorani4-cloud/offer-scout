import unittest
from helpers import settings
from offer_scout.compliance import ComplianceScreen


class ComplianceTests(unittest.TestCase):
    def setUp(self):
        self.screen = ComplianceScreen(settings().compliance)

    def test_autism_diet_rejected_and_routed_to_blocked_niche(self):
        r = self.screen.evaluate("Autism Gluten Free Casein Free Diet Meal Plan Printable")
        self.assertTrue(r.hard_reject)
        self.assertEqual(r.assign_subcategory, "autism_nutrition_intervention")
        self.assertEqual(r.health_risk, "high")

    def test_autism_organizer_is_not_hard_rejected(self):
        r = self.screen.evaluate("Special Needs Binder Printable: appointments, school meeting notes, routines")
        self.assertFalse(r.hard_reject)

    def test_pet_sitter_template_passes(self):
        r = self.screen.evaluate("Pet Sitter Business Template | Dog Walking Spreadsheet | Instant Download")
        self.assertFalse(r.hard_reject)
        self.assertEqual(r.flags, [])

    def test_dog_treats_is_not_a_clinical_claim(self):
        self.assertFalse(self.screen.evaluate("Dog treats recipe card printable").hard_reject)

    def test_vet_dosage_rejected(self):
        r = self.screen.evaluate("Dog medication dosage chart for common ailments")
        self.assertTrue(r.hard_reject)
        self.assertEqual(r.veterinary_risk, "high")

    def test_condition_specific_variants_rejected(self):
        self.assertTrue(self.screen.evaluate("Cancer care planner treatment tracker").hard_reject)
        self.assertTrue(self.screen.evaluate("Dementia caregiver daily log").hard_reject)

    def test_academic_fraud_rejected(self):
        self.assertTrue(self.screen.evaluate("Undetectable essay writer bypass AI detector").hard_reject)

    def test_supplement_and_weight_loss_rejected(self):
        self.assertTrue(self.screen.evaluate("30 day weight loss meal plan").hard_reject)
        self.assertTrue(self.screen.evaluate("Daily supplement protocol tracker").hard_reject)

    def test_adjacent_terms_flag_but_do_not_reject(self):
        r = self.screen.evaluate("ADHD focus planner printable with weekly habit tracker")
        self.assertFalse(r.hard_reject)
        self.assertIn("condition_adjacent", r.flags)
        self.assertEqual(r.health_risk, "low")

    def test_ip_brand_rejected(self):
        self.assertTrue(self.screen.evaluate("Disney princess study planner").hard_reject)


if __name__ == "__main__":
    unittest.main()
