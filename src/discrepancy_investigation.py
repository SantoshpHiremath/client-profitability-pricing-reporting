"""Cross-system reconciliation: does the invoice match what the contract says it should be?

This is the direct analogue of the UL Solutions discrepancy-investigation work:
two linked records (contract, invoice) that are supposed to agree, checked
against each other explicitly, with mismatches classified by likely root
cause rather than just reported as "wrong."
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from typing import Optional

from src.models import Dataset

MATERIALITY_THRESHOLD = 0.01  # 1% relative difference before we flag anything


@dataclass
class DiscrepancyFlag:
    invoice_id: str
    contract_id: str
    month: date
    expected_amount: float
    actual_amount: float
    delta: float
    delta_pct: float
    root_cause: str  # "rebate_not_reflected" | "duplicate_line" | "orphaned_invoice" | "unclassified"


def _days_in_month(d: date) -> int:
    return calendar.monthrange(d.year, d.month)[1]


def expected_amount_for(contract, month: date, pricing_measures_by_id: dict) -> float:
    """The amount an invoice *should* bill for this contract in this month,
    accounting for any active pricing measure and pro-ration on the final month.
    Both the days-elapsed and days-in-month figures are derived from the SAME
    month (the invoice's own month) -- see README bug #1 for why that matters.
    """
    rate = contract.monthly_rate
    if contract.pricing_measure_id:
        pm = pricing_measures_by_id.get(contract.pricing_measure_id)
        if pm and month >= pm.effective_date:
            effect = {"PM-001": 1.06, "PM-002": 0.92, "PM-003": 0.90, "PM-004": 1.05}[pm.measure_id]
            rate = round(rate * effect, 2)

    if contract.end_date and contract.end_date.year == month.year and contract.end_date.month == month.month:
        dim = _days_in_month(month)
        days_active = contract.end_date.day
        return round(rate * days_active / dim, 2)

    return rate


def investigate_discrepancies(dataset: Dataset) -> list:
    """Cross-checks every invoice against its contract. Returns a list of
    DiscrepancyFlag for anything that doesn't reconcile, including invoices
    whose contract_id doesn't exist at all (orphaned invoices), which are
    surfaced explicitly rather than skipped or allowed to crash the join.
    """
    contracts_by_id = {c.contract_id: c for c in dataset.contracts}
    pricing_measures_by_id = {pm.measure_id: pm for pm in dataset.pricing_measures}
    flags = []

    seen_amount_month_contract = {}  # (contract_id, month) -> first invoice_id seen, to detect duplicates

    for inv in dataset.invoices:
        contract = contracts_by_id.get(inv.contract_id)

        if contract is None:
            flags.append(DiscrepancyFlag(
                invoice_id=inv.invoice_id, contract_id=inv.contract_id, month=inv.month,
                expected_amount=0.0, actual_amount=inv.amount,
                delta=inv.amount, delta_pct=1.0, root_cause="orphaned_invoice",
            ))
            continue

        key = (inv.contract_id, inv.month)
        if key in seen_amount_month_contract:
            flags.append(DiscrepancyFlag(
                invoice_id=inv.invoice_id, contract_id=inv.contract_id, month=inv.month,
                expected_amount=0.0, actual_amount=inv.amount,
                delta=inv.amount, delta_pct=1.0, root_cause="duplicate_line",
            ))
            continue
        seen_amount_month_contract[key] = inv.invoice_id

        expected = expected_amount_for(contract, inv.month, pricing_measures_by_id)
        delta = round(inv.amount - expected, 2)
        delta_pct = abs(delta) / expected if expected else (1.0 if delta else 0.0)

        if delta_pct <= MATERIALITY_THRESHOLD:
            continue  # reconciles within materiality -- no flag

        root_cause = "rebate_not_reflected" if delta < 0 else "unclassified"
        flags.append(DiscrepancyFlag(
            invoice_id=inv.invoice_id, contract_id=inv.contract_id, month=inv.month,
            expected_amount=expected, actual_amount=inv.amount,
            delta=delta, delta_pct=round(delta_pct, 4), root_cause=root_cause,
        ))

    return flags


def reconciled_amount(inv, flags_by_invoice_id: dict) -> Optional[float]:
    """The amount to use for downstream profitability reporting: the invoice's
    actual amount is trusted UNLESS it's a duplicate (excluded entirely) or
    orphaned (excluded -- no contract to attribute revenue to).
    """
    flag = flags_by_invoice_id.get(inv.invoice_id)
    if flag and flag.root_cause in ("duplicate_line", "orphaned_invoice"):
        return None
    return inv.amount
