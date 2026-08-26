from datetime import date

from src.models import Customer, Product, Contract, Invoice, PricingMeasure, Dataset


def small_clean_dataset() -> Dataset:
    """A tiny hand-built dataset with a known, hand-computable answer: no
    discrepancies, used as the baseline "everything reconciles" case.
    """
    customers = [Customer("C1", "Acme Fleet GmbH", "DE"), Customer("C2", "Beta Logistics BV", "NL")]
    products = [Product("P1", "Compact Sedan Lease", "passenger")]
    contracts = [
        Contract("CTR-1", "C1", "P1", "DE", 300.0, date(2025, 1, 1), None),
        Contract("CTR-2", "C2", "P1", "DE", 400.0, date(2025, 1, 1), None),  # international: NL customer, DE entity
    ]
    invoices = [
        Invoice("INV-1", "CTR-1", date(2025, 1, 1), 300.0, 180.0),
        Invoice("INV-2", "CTR-1", date(2025, 2, 1), 300.0, 180.0),
        Invoice("INV-3", "CTR-2", date(2025, 1, 1), 400.0, 250.0),
    ]
    return Dataset(customers=customers, products=products, contracts=contracts,
                    invoices=invoices, pricing_measures=[])


def dataset_with_rebate_discrepancy() -> Dataset:
    """CTR-1's February invoice bills 12% below contract rate -- an unreflected
    rebate, the exact UL-Solutions-shaped discrepancy this project targets.
    """
    ds = small_clean_dataset()
    ds.invoices[1].amount = round(300.0 * 0.88, 2)  # 264.00 instead of 300.0
    return ds


def dataset_with_duplicate_invoice() -> Dataset:
    ds = small_clean_dataset()
    dup = Invoice("INV-1B", "CTR-1", date(2025, 1, 1), 300.0, 180.0, is_duplicate_of="INV-1")
    ds.invoices.append(dup)
    return ds


def dataset_with_orphaned_invoice() -> Dataset:
    ds = small_clean_dataset()
    ds.invoices.append(Invoice("INV-ORPHAN", "CTR-999", date(2025, 1, 1), 100.0, 60.0))
    return ds


def dataset_with_prorated_final_month() -> Dataset:
    """CTR-1 ends on Feb 15, 2025 (28-day Feb, non-leap year) -- its final
    invoice should be pro-rated to 15/28 of the monthly rate.
    """
    ds = small_clean_dataset()
    ds.contracts[0].end_date = date(2025, 2, 15)
    expected_final = round(300.0 * 15 / 28, 2)
    ds.invoices[1].amount = expected_final
    return ds


def dataset_with_pricing_measure() -> Dataset:
    """PM-EFFECT: applies to CTR-1 only from March 2025, a +10% increase.
    CTR-2 is untagged and its revenue moves in the OPPOSITE direction across
    the same period -- if the pricing-effect calc accidentally includes
    untagged contracts, this fixture will make that visible (bug #2 regression).
    """
    ds = small_clean_dataset()
    ds.pricing_measures = [
        PricingMeasure("PM-EFFECT", "Test rate increase +10%", date(2025, 3, 1), ["CTR-1"]),
    ]
    ds.contracts[0].pricing_measure_id = "PM-EFFECT"
    ds.invoices = [
        Invoice("INV-1", "CTR-1", date(2025, 1, 1), 300.0, 180.0),
        Invoice("INV-2", "CTR-1", date(2025, 2, 1), 300.0, 180.0),
        Invoice("INV-3", "CTR-1", date(2025, 3, 1), 330.0, 200.0),  # +10%
        Invoice("INV-4", "CTR-1", date(2025, 4, 1), 330.0, 200.0),
        # CTR-2 untagged: revenue DROPS over the same window (opposite direction)
        Invoice("INV-5", "CTR-2", date(2025, 1, 1), 400.0, 250.0),
        Invoice("INV-6", "CTR-2", date(2025, 2, 1), 400.0, 250.0),
        Invoice("INV-7", "CTR-2", date(2025, 3, 1), 300.0, 180.0),
        Invoice("INV-8", "CTR-2", date(2025, 4, 1), 300.0, 180.0),
    ]
    return ds


def dataset_with_unaffected_pricing_measure() -> Dataset:
    """A pricing measure with zero tagged contracts -- must return insufficient_data, not crash."""
    ds = small_clean_dataset()
    ds.pricing_measures = [
        PricingMeasure("PM-EMPTY", "Unused measure", date(2025, 3, 1), []),
    ]
    return ds
