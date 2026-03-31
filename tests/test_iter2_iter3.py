"""
test_iter2_iter3.py — Tests for Iteration 2 (Diff Engine) and Iteration 3 (Template Populator).

Run with:
    python tests/test_iter2_iter3.py

Or via pytest:
    python -m pytest tests/test_iter2_iter3.py -v
"""

import sys
import json
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.diff.field_extractor import FieldExtractor, RiskLevel
from src.diff.diff_engine import DiffEngine, ChangeType, print_diff_report
from src.generator.template_populator import TemplatePopulator, TradeData


# ─── Sample Documents ─────────────────────────────────────────────────────

TEMPLATE_TEXT = """TRADE CONFIRMATION
Date: March 1, 2026
Trade Type: Interest Rate Swap
Product: Vanilla IRS
Parties: Goldman Sachs and ABC Capital LLC
Counterparty: Goldman Sachs
Jurisdiction: US
Governing Law: New York
ISDA Agreement: 2002 ISDA Master Agreement
Notional Amount: USD 50,000,000
Fixed Rate: 4.25% per annum
Floating Rate: SOFR + 25bps
Payment Frequency: Quarterly
Effective Date: April 1, 2026
Maturity Date: April 1, 2031
Day Count: Actual/360
Version: v1
Status: active
"""

INCOMING_SAME = TEMPLATE_TEXT  # Identical — expect 0 discrepancies

INCOMING_CHANGED = """TRADE CONFIRMATION
Date: March 5, 2026
Trade Type: Interest Rate Swap
Product: Vanilla IRS
Parties: Goldman Sachs and ABC Capital LLC
Counterparty: Goldman Sachs
Jurisdiction: US
Governing Law: English
ISDA Agreement: 2002 ISDA Master Agreement
Notional Amount: USD 75,000,000
Fixed Rate: 5.00% per annum
Floating Rate: SOFR + 50bps
Payment Frequency: Semi-Annual
Effective Date: April 1, 2026
Maturity Date: April 1, 2036
Day Count: Actual/365
Version: v2
Status: draft
"""

INCOMING_MISSING = """TRADE CONFIRMATION
Date: March 5, 2026
Trade Type: Interest Rate Swap
Counterparty: Goldman Sachs
Jurisdiction: US
Version: v1
Status: active
"""

FX_TEXT = """TRADE CONFIRMATION
Date: March 1, 2026
Trade Type: FX Forward
Product: FX Forward
Parties: HSBC and ABC Capital LLC
Counterparty: HSBC
Jurisdiction: UK
Governing Law: English
ISDA Agreement: 2002 ISDA Master Agreement
Notional Amount: GBP 10,000,000
Effective Date: April 5, 2026
Maturity Date: October 5, 2026
Payment Frequency: At Maturity
Version: v1
Status: active
"""


# ══════════════════════════════════════════════════════════════════════════
#  ITERATION 2: FIELD EXTRACTOR TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestFieldExtractor(unittest.TestCase):

    def setUp(self):
        self.extractor = FieldExtractor()

    def test_extracts_economic_fields(self):
        doc = self.extractor.extract_from_text(TEMPLATE_TEXT, "template.docx")
        self.assertEqual(doc.get("notional_amount").value, "USD 50,000,000")
        self.assertEqual(doc.get("fixed_rate").value,      "4.25% per annum")
        self.assertEqual(doc.get("floating_rate").value,   "SOFR + 25bps")
        self.assertEqual(doc.get("effective_date").value,  "April 1, 2026")
        self.assertEqual(doc.get("maturity_date").value,   "April 1, 2031")
        self.assertEqual(doc.get("payment_frequency").value, "Quarterly")
        self.assertEqual(doc.get("day_count").value,       "Actual/360")

    def test_extracts_legal_fields(self):
        doc = self.extractor.extract_from_text(TEMPLATE_TEXT)
        self.assertEqual(doc.get("governing_law").value, "New York")
        self.assertEqual(doc.get("isda_version").value,  "2002 ISDA Master Agreement")
        self.assertEqual(doc.get("trade_type").value,    "Interest Rate Swap")

    def test_extracts_counterparty_fields(self):
        doc = self.extractor.extract_from_text(TEMPLATE_TEXT)
        self.assertEqual(doc.get("counterparty").value, "Goldman Sachs")
        self.assertEqual(doc.get("jurisdiction").value, "US")

    def test_missing_fields_marked_not_found(self):
        doc = self.extractor.extract_from_text(INCOMING_MISSING)
        self.assertFalse(doc.get("notional_amount").found)
        self.assertFalse(doc.get("fixed_rate").found)
        self.assertFalse(doc.get("governing_law").found)

    def test_by_category(self):
        doc = self.extractor.extract_from_text(TEMPLATE_TEXT)
        economic = doc.by_category("economic")
        self.assertGreater(len(economic), 0)
        self.assertTrue(all(f.category == "economic" for f in economic))

    def test_by_risk(self):
        doc = self.extractor.extract_from_text(TEMPLATE_TEXT)
        high = doc.by_risk(RiskLevel.HIGH)
        self.assertGreater(len(high), 0)
        self.assertTrue(all(f.risk_level == RiskLevel.HIGH for f in high))

    def test_filename_stored(self):
        doc = self.extractor.extract_from_text(TEMPLATE_TEXT, "my_file.docx")
        self.assertEqual(doc.filename, "my_file.docx")

    def test_fx_fields_extracted(self):
        doc = self.extractor.extract_from_text(FX_TEXT)
        self.assertEqual(doc.get("trade_type").value, "FX Forward")
        self.assertEqual(doc.get("notional_amount").value, "GBP 10,000,000")
        self.assertEqual(doc.get("governing_law").value, "English")


# ══════════════════════════════════════════════════════════════════════════
#  ITERATION 2: DIFF ENGINE TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestDiffEngine(unittest.TestCase):

    def setUp(self):
        self.extractor = FieldExtractor()
        self.engine    = DiffEngine()

    def _compare(self, text_a, text_b):
        return self.engine.compare_texts(text_a, text_b)

    def test_identical_docs_produce_zero_discrepancies(self):
        report = self._compare(TEMPLATE_TEXT, INCOMING_SAME)
        self.assertEqual(report.total_discrepancies, 0)
        self.assertGreater(len(report.matches), 0)

    def test_changed_fields_detected(self):
        report = self._compare(TEMPLATE_TEXT, INCOMING_CHANGED)
        self.assertGreater(report.total_discrepancies, 0)

    def test_high_risk_fields_detected(self):
        report = self._compare(TEMPLATE_TEXT, INCOMING_CHANGED)
        self.assertGreater(len(report.high_risk), 0)

    def test_governing_law_change_is_high_risk(self):
        report = self._compare(TEMPLATE_TEXT, INCOMING_CHANGED)
        disc = next((d for d in report.discrepancies if d.field_key == "governing_law"), None)
        self.assertIsNotNone(disc)
        self.assertEqual(disc.risk_level, RiskLevel.HIGH)

    def test_numeric_drift_detected_for_notional(self):
        report = self._compare(TEMPLATE_TEXT, INCOMING_CHANGED)
        disc = next((d for d in report.discrepancies if d.field_key == "notional_amount"), None)
        self.assertIsNotNone(disc)
        self.assertEqual(disc.change_type, ChangeType.NUMERIC_DRIFT)
        self.assertIsNotNone(disc.numeric_pct)
        self.assertAlmostEqual(disc.numeric_pct, 50.0, delta=1.0)  # 50M → 75M = +50%

    def test_numeric_drift_for_fixed_rate(self):
        report = self._compare(TEMPLATE_TEXT, INCOMING_CHANGED)
        disc = next((d for d in report.discrepancies if d.field_key == "fixed_rate"), None)
        self.assertIsNotNone(disc)
        self.assertEqual(disc.change_type, ChangeType.NUMERIC_DRIFT)

    def test_missing_fields_flagged(self):
        report = self._compare(TEMPLATE_TEXT, INCOMING_MISSING)
        missing = [d for d in report.discrepancies if d.change_type == ChangeType.MISSING]
        self.assertGreater(len(missing), 0)
        missing_keys = [m.field_key for m in missing]
        self.assertIn("notional_amount", missing_keys)
        self.assertIn("fixed_rate", missing_keys)

    def test_missing_fields_inherit_risk_level(self):
        report = self._compare(TEMPLATE_TEXT, INCOMING_MISSING)
        notional_disc = next(
            (d for d in report.discrepancies if d.field_key == "notional_amount"), None)
        self.assertIsNotNone(notional_disc)
        self.assertEqual(notional_disc.risk_level, RiskLevel.HIGH)

    def test_risk_score_higher_for_more_changes(self):
        report_same    = self._compare(TEMPLATE_TEXT, INCOMING_SAME)
        report_changed = self._compare(TEMPLATE_TEXT, INCOMING_CHANGED)
        self.assertGreater(report_changed.risk_score, report_same.risk_score)

    def test_needs_review_true_when_high_risk(self):
        report = self._compare(TEMPLATE_TEXT, INCOMING_CHANGED)
        self.assertTrue(report.needs_review)

    def test_needs_review_false_when_identical(self):
        report = self._compare(TEMPLATE_TEXT, INCOMING_SAME)
        self.assertFalse(report.needs_review)

    def test_discrepancies_sorted_high_first(self):
        report = self._compare(TEMPLATE_TEXT, INCOMING_CHANGED)
        levels = [d.risk_level for d in report.discrepancies]
        order  = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        for i in range(len(levels) - 1):
            self.assertLessEqual(order[levels[i]], order[levels[i+1]])

    def test_to_dict_serialisable(self):
        report = self._compare(TEMPLATE_TEXT, INCOMING_CHANGED)
        d = report.to_dict()
        serialised = json.dumps(d)  # Should not raise
        self.assertIn("discrepancies", d)
        self.assertIn("risk_score", d)

    def test_cross_trade_type_many_differences(self):
        report = self._compare(TEMPLATE_TEXT, FX_TEXT)
        # Different trade types, different economic terms — should have many diffs
        self.assertGreater(report.total_discrepancies, 3)

    def test_explanation_populated_for_changes(self):
        report = self._compare(TEMPLATE_TEXT, INCOMING_CHANGED)
        for d in report.discrepancies:
            if d.change_type in (ChangeType.CHANGED, ChangeType.NUMERIC_DRIFT, ChangeType.MISSING):
                self.assertIsNotNone(d.explanation)
                self.assertGreater(len(d.explanation), 0)

    def test_similarity_score_between_0_and_1(self):
        report = self._compare(TEMPLATE_TEXT, INCOMING_CHANGED)
        for d in report.discrepancies:
            if d.similarity is not None:
                self.assertGreaterEqual(d.similarity, 0.0)
                self.assertLessEqual(d.similarity, 1.0)


# ══════════════════════════════════════════════════════════════════════════
#  ITERATION 3: TRADE DATA TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestTradeData(unittest.TestCase):

    def test_from_dict(self):
        td = TradeData.from_dict({
            "trade_type": "Interest Rate Swap",
            "counterparty": "Goldman Sachs",
            "currency": "USD",
        })
        self.assertEqual(td.trade_type,   "Interest Rate Swap")
        self.assertEqual(td.counterparty, "Goldman Sachs")
        self.assertEqual(td.currency,     "USD")

    def test_from_dict_extras(self):
        td = TradeData.from_dict({"trade_type": "IRS", "custom_field": "value"})
        self.assertEqual(td.extras.get("custom_field"), "value")

    def test_from_json(self):
        js = json.dumps({"trade_type": "FX Forward", "currency": "GBP"})
        td = TradeData.from_json(js)
        self.assertEqual(td.trade_type, "FX Forward")
        self.assertEqual(td.currency,   "GBP")

    def test_to_dict_round_trip(self):
        td = TradeData.from_dict({"trade_type": "IRS", "notional_amount": "USD 50M"})
        d  = td.to_dict()
        self.assertEqual(d["trade_type"],     "IRS")
        self.assertEqual(d["notional_amount"], "USD 50M")

    def test_empty_fields_default_to_empty_string(self):
        td = TradeData()
        self.assertEqual(td.trade_type, "")
        self.assertEqual(td.notional_amount, "")


# ══════════════════════════════════════════════════════════════════════════
#  ITERATION 3: TEMPLATE POPULATOR TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestTemplatePopulator(unittest.TestCase):

    def setUp(self):
        from src.template_generator import generate_all_templates
        generate_all_templates()
        self.populator = TemplatePopulator()

    def _irs_trade(self, **overrides):
        base = {
            "trade_type":      "Interest Rate Swap",
            "counterparty":    "Goldman Sachs",
            "currency":        "USD",
            "notional_amount": "USD 50,000,000",
            "fixed_rate":      "4.25% per annum",
            "effective_date":  "April 1, 2026",
            "maturity_date":   "April 1, 2031",
            "jurisdiction":    "US",
            "party_a":         "Goldman Sachs Bank USA",
            "party_b":         "ABC Capital LLC",
        }
        base.update(overrides)
        return base

    # Stage 1: Auto-fill
    def test_autofill_injects_counterparty(self):
        result = self.populator.generate(self._irs_trade())
        self.assertIn("Goldman Sachs", result.populated_text)

    def test_autofill_injects_notional(self):
        result = self.populator.generate(self._irs_trade())
        self.assertIn("USD 50,000,000", result.populated_text)

    def test_autofill_count_positive(self):
        result = self.populator.generate(self._irs_trade())
        self.assertGreater(result.autofill_count, 0)

    def test_autofill_injects_dates(self):
        result = self.populator.generate(self._irs_trade())
        self.assertIn("April 1, 2026", result.populated_text)
        self.assertIn("April 1, 2031", result.populated_text)

    # Stage 2: AI clause suggestions
    def test_governing_law_suggested_for_us_jurisdiction(self):
        result = self.populator.generate(self._irs_trade())
        self.assertEqual(result.trade_data.governing_law, "New York")

    def test_isda_version_suggested_for_irs(self):
        result = self.populator.generate(self._irs_trade())
        self.assertIn("2002", result.trade_data.isda_version)

    def test_day_count_suggested_for_usd(self):
        result = self.populator.generate(self._irs_trade())
        self.assertEqual(result.trade_data.day_count, "Actual/360")

    def test_floating_rate_suggested_for_usd(self):
        result = self.populator.generate(self._irs_trade())
        self.assertIn("SOFR", result.trade_data.floating_rate)

    def test_clearing_venue_suggested_for_irs(self):
        result = self.populator.generate(self._irs_trade())
        self.assertIn("LCH", result.trade_data.clearing_venue)

    def test_payment_frequency_suggested(self):
        result = self.populator.generate(self._irs_trade())
        self.assertEqual(result.trade_data.payment_frequency, "Quarterly")

    def test_ai_clause_count_positive(self):
        result = self.populator.generate(self._irs_trade())
        self.assertGreater(result.ai_clause_count, 0)

    def test_uk_jurisdiction_suggests_english_law(self):
        result = self.populator.generate({
            "trade_type": "FX Forward", "currency": "GBP",
            "jurisdiction": "UK", "counterparty": "HSBC",
        })
        self.assertEqual(result.trade_data.governing_law, "English")

    def test_gbp_day_count_is_actual_365(self):
        result = self.populator.generate({
            "trade_type": "FX Forward", "currency": "GBP", "jurisdiction": "UK",
        })
        self.assertEqual(result.trade_data.day_count, "Actual/365")

    def test_cds_roles_suggested(self):
        result = self.populator.generate({
            "trade_type": "Credit Default Swap",
            "currency": "USD", "jurisdiction": "US",
        })
        self.assertEqual(result.trade_data.party_a_role, "Protection Seller")
        self.assertEqual(result.trade_data.party_b_role, "Protection Buyer")

    def test_manual_override_not_replaced(self):
        result = self.populator.generate(self._irs_trade(governing_law="French"))
        self.assertEqual(result.trade_data.governing_law, "French")

    # Stage 3: Validation
    def test_valid_trade_has_no_errors(self):
        result = self.populator.generate(self._irs_trade())
        self.assertEqual(len(result.errors), 0)

    def test_missing_governing_law_raises_error_after_suggestion(self):
        # Force no jurisdiction so no governing_law is suggested
        result = self.populator.generate({
            "trade_type": "Interest Rate Swap",
            "notional_amount": "USD 50M",
        })
        # After suggestions, governing_law may still be empty if no jurisdiction
        if not result.trade_data.governing_law:
            error_fields = [e.field for e in result.errors]
            self.assertIn("governing_law", error_fields)

    def test_inverted_dates_produce_error(self):
        result = self.populator.generate(self._irs_trade(
            effective_date="April 1, 2031",
            maturity_date="April 1, 2026",   # maturity BEFORE effective
        ))
        error_fields = [e.field for e in result.errors]
        self.assertIn("effective_date", error_fields)

    def test_validation_score_high_for_complete_trade(self):
        result = self.populator.generate(self._irs_trade())
        self.assertGreater(result.validation_score, 50)

    def test_validation_score_low_for_empty_trade(self):
        result = self.populator.generate({})
        self.assertLess(result.validation_score, 50)

    def test_is_valid_true_for_good_trade(self):
        result = self.populator.generate(self._irs_trade())
        self.assertTrue(result.is_valid)

    def test_filename_generated(self):
        result = self.populator.generate(self._irs_trade())
        self.assertTrue(result.filename.endswith(".docx"))
        self.assertIn("Goldman", result.filename)

    def test_from_json_string(self):
        js = json.dumps(self._irs_trade())
        result = self.populator.generate_from_json(js)
        self.assertIsNotNone(result)
        self.assertGreater(result.autofill_count, 0)

    def test_populated_text_contains_trade_type(self):
        result = self.populator.generate(self._irs_trade())
        self.assertIn("Interest Rate Swap", result.populated_text)


# ─── Runner ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  ITERATION 2 & 3 — TEST SUITE")
    print("="*60)

    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()

    for cls in [TestFieldExtractor, TestDiffEngine, TestTradeData, TestTemplatePopulator]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    passed = result.testsRun - len(result.failures) - len(result.errors)
    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{result.testsRun} passed")
    if result.failures or result.errors:
        print("  ⚠  Some tests failed — check output above")
    else:
        print("  ✅ All tests passed")
    print(f"{'='*60}\n")

    sys.exit(0 if not result.failures and not result.errors else 1)
