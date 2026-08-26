from src.discrepancy_investigation import investigate_discrepancies
from tests.fixtures import (
    small_clean_dataset, dataset_with_rebate_discrepancy, dataset_with_duplicate_invoice,
    dataset_with_orphaned_invoice, dataset_with_prorated_final_month,
)


class TestCleanData:
    def test_clean_matching_invoices_produce_no_flags(self):
        flags = investigate_discrepancies(small_clean_dataset())
        assert flags == []


class TestRebateDiscrepancy:
    def test_unreflected_rebate_is_flagged(self):
        flags = investigate_discrepancies(dataset_with_rebate_discrepancy())
        assert len(flags) == 1
        assert flags[0].invoice_id == "INV-2"

    def test_unreflected_rebate_is_classified_correctly(self):
        flags = investigate_discrepancies(dataset_with_rebate_discrepancy())
        assert flags[0].root_cause == "rebate_not_reflected"

    def test_rebate_delta_is_negative_and_correct_magnitude(self):
        flags = investigate_discrepancies(dataset_with_rebate_discrepancy())
        # expected 300.0, actual 264.0 -> delta -36.0
        assert flags[0].expected_amount == 300.0
        assert flags[0].actual_amount == 264.0
        assert flags[0].delta == -36.0


class TestDuplicateInvoice:
    def test_duplicate_invoice_line_is_flagged(self):
        flags = investigate_discrepancies(dataset_with_duplicate_invoice())
        causes = [f.root_cause for f in flags]
        assert "duplicate_line" in causes

    def test_duplicate_flag_references_the_second_invoice(self):
        flags = investigate_discrepancies(dataset_with_duplicate_invoice())
        dup_flags = [f for f in flags if f.root_cause == "duplicate_line"]
        assert len(dup_flags) == 1
        assert dup_flags[0].invoice_id == "INV-1B"


class TestOrphanedInvoice:
    def test_orphaned_invoice_is_surfaced_not_dropped(self):
        flags = investigate_discrepancies(dataset_with_orphaned_invoice())
        orphan_flags = [f for f in flags if f.root_cause == "orphaned_invoice"]
        assert len(orphan_flags) == 1
        assert orphan_flags[0].invoice_id == "INV-ORPHAN"
        assert orphan_flags[0].contract_id == "CTR-999"

    def test_investigation_does_not_crash_on_missing_contract(self):
        # Would raise KeyError if the join weren't done defensively.
        investigate_discrepancies(dataset_with_orphaned_invoice())


class TestProration:
    def test_prorated_final_month_matches_exactly(self):
        """Regression test for bug #1 (pro-ration off-by-one): both the
        days-elapsed and days-in-month figures must come from the SAME month.
        """
        flags = investigate_discrepancies(dataset_with_prorated_final_month())
        assert flags == []  # must reconcile exactly, not be flagged as discrepant
