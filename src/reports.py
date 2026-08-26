"""Assembles the ad-hoc stakeholder reports a Finance team would actually request."""
from __future__ import annotations

from dataclasses import dataclass

from src.discrepancy_investigation import investigate_discrepancies
from src.models import Dataset
from src.pricing_effect import measure_pricing_effect
from src.profitability import (
    profitability_by_customer, profitability_by_product, profitability_local_vs_international,
)


@dataclass
class ProfitabilitySummary:
    by_customer: list
    by_product: list
    local_vs_international: list
    total_revenue: float
    total_margin: float


@dataclass
class FullReport:
    discrepancy_flags: list
    profitability: ProfitabilitySummary
    pricing_effects: list


def build_profitability_summary(dataset: Dataset) -> ProfitabilitySummary:
    by_customer = profitability_by_customer(dataset)
    by_product = profitability_by_product(dataset)
    local_vs_intl = profitability_local_vs_international(dataset)
    total_revenue = round(sum(r.revenue for r in by_customer), 2)
    total_margin = round(sum(r.margin for r in by_customer), 2)
    return ProfitabilitySummary(
        by_customer=by_customer, by_product=by_product, local_vs_international=local_vs_intl,
        total_revenue=total_revenue, total_margin=total_margin,
    )


def build_full_report(dataset: Dataset) -> FullReport:
    flags = investigate_discrepancies(dataset)
    profitability = build_profitability_summary(dataset)
    pricing_effects = measure_pricing_effect(dataset)
    return FullReport(discrepancy_flags=flags, profitability=profitability, pricing_effects=pricing_effects)
