"""Measuring the effect of a pricing measure over time -- on the contracts it
actually applies to, compared against a naive whole-portfolio baseline.

This is observational, not a controlled experiment: there is no randomized
control group, so this module reports before/after differences on the
affected population and is explicit that it cannot claim causality the way
pricing-ab-test-analysis's randomized-experiment approach can.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from src.models import Dataset


@dataclass
class PricingEffectResult:
    measure_id: str
    description: str
    effective_date: date
    affected_contract_count: int
    avg_monthly_revenue_before: Optional[float]
    avg_monthly_revenue_after: Optional[float]
    pct_change: Optional[float]
    retained_contract_count: int  # contracts still active as of the last month in the dataset
    retention_rate: Optional[float]
    insufficient_data: bool = False


def _monthly_revenue_by_contract(dataset: Dataset, contract_ids: set, before: bool, effective_date: date) -> dict:
    """Average monthly invoice amount per contract, restricted to months
    strictly before (or on/after) the pricing measure's effective date.
    """
    totals = {}
    counts = {}
    for inv in dataset.invoices:
        if inv.contract_id not in contract_ids:
            continue
        is_before = inv.month < effective_date
        if is_before != before:
            continue
        totals[inv.contract_id] = totals.get(inv.contract_id, 0.0) + inv.amount
        counts[inv.contract_id] = counts.get(inv.contract_id, 0) + 1

    return {cid: totals[cid] / counts[cid] for cid in totals}


def measure_pricing_effect(dataset: Dataset) -> list:
    results = []
    last_month = max((inv.month for inv in dataset.invoices), default=None)

    for pm in dataset.pricing_measures:
        affected_ids = set(pm.affected_contract_ids)

        if not affected_ids:
            results.append(PricingEffectResult(
                measure_id=pm.measure_id, description=pm.description, effective_date=pm.effective_date,
                affected_contract_count=0, avg_monthly_revenue_before=None, avg_monthly_revenue_after=None,
                pct_change=None, retained_contract_count=0, retention_rate=None, insufficient_data=True,
            ))
            continue

        before_by_contract = _monthly_revenue_by_contract(dataset, affected_ids, before=True, effective_date=pm.effective_date)
        after_by_contract = _monthly_revenue_by_contract(dataset, affected_ids, before=False, effective_date=pm.effective_date)

        if not before_by_contract or not after_by_contract:
            results.append(PricingEffectResult(
                measure_id=pm.measure_id, description=pm.description, effective_date=pm.effective_date,
                affected_contract_count=len(affected_ids), avg_monthly_revenue_before=None,
                avg_monthly_revenue_after=None, pct_change=None,
                retained_contract_count=0, retention_rate=None, insufficient_data=True,
            ))
            continue

        avg_before = round(sum(before_by_contract.values()) / len(before_by_contract), 2)
        avg_after = round(sum(after_by_contract.values()) / len(after_by_contract), 2)
        pct_change = round((avg_after - avg_before) / avg_before, 4) if avg_before else None

        contracts_by_id = {c.contract_id: c for c in dataset.contracts}
        retained = sum(
            1 for cid in affected_ids
            if cid in contracts_by_id and (contracts_by_id[cid].end_date is None or contracts_by_id[cid].end_date >= last_month)
        )
        retention_rate = round(retained / len(affected_ids), 4) if affected_ids else None

        results.append(PricingEffectResult(
            measure_id=pm.measure_id, description=pm.description, effective_date=pm.effective_date,
            affected_contract_count=len(affected_ids), avg_monthly_revenue_before=avg_before,
            avg_monthly_revenue_after=avg_after, pct_change=pct_change,
            retained_contract_count=retained, retention_rate=retention_rate, insufficient_data=False,
        ))

    return results
