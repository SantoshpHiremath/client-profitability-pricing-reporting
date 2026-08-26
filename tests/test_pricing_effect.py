from src.pricing_effect import measure_pricing_effect
from tests.fixtures import dataset_with_pricing_measure, dataset_with_unaffected_pricing_measure


class TestBeforeAfterComputation:
    def test_before_after_averages_match_hand_computed_answer(self):
        results = measure_pricing_effect(dataset_with_pricing_measure())
        r = next(r for r in results if r.measure_id == "PM-EFFECT")
        # CTR-1 before (Jan, Feb): (300+300)/2 = 300.0
        # CTR-1 after (Mar, Apr): (330+330)/2 = 330.0
        assert r.avg_monthly_revenue_before == 300.0
        assert r.avg_monthly_revenue_after == 330.0
        assert r.pct_change == 0.1

    def test_affected_contract_count_is_correct(self):
        results = measure_pricing_effect(dataset_with_pricing_measure())
        r = next(r for r in results if r.measure_id == "PM-EFFECT")
        assert r.affected_contract_count == 1


class TestOnlyAffectedContractsCounted:
    def test_untagged_contract_does_not_change_the_reported_effect(self):
        """Regression test for bug #2: CTR-2 (untagged) drops in revenue over
        the same window. If the calculation incorrectly pooled all contracts,
        the reported effect for PM-EFFECT would be diluted below +10%.
        """
        results = measure_pricing_effect(dataset_with_pricing_measure())
        r = next(r for r in results if r.measure_id == "PM-EFFECT")
        assert r.pct_change == 0.1  # exactly CTR-1's own change, unaffected by CTR-2


class TestRetention:
    def test_retention_counts_contracts_still_active_at_last_month(self):
        results = measure_pricing_effect(dataset_with_pricing_measure())
        r = next(r for r in results if r.measure_id == "PM-EFFECT")
        assert r.retained_contract_count == 1
        assert r.retention_rate == 1.0


class TestInsufficientData:
    def test_measure_with_zero_affected_contracts_is_marked_insufficient(self):
        results = measure_pricing_effect(dataset_with_unaffected_pricing_measure())
        r = next(r for r in results if r.measure_id == "PM-EMPTY")
        assert r.insufficient_data is True
        assert r.avg_monthly_revenue_before is None
        assert r.pct_change is None

    def test_insufficient_data_does_not_raise_division_by_zero(self):
        # Would raise ZeroDivisionError if not guarded.
        measure_pricing_effect(dataset_with_unaffected_pricing_measure())
