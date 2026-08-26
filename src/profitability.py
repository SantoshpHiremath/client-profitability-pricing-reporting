"""Profitability KPI reporting by customer and by product, local vs. international.

Computed from the RECONCILED invoice set (post discrepancy-investigation),
not the raw feed -- this module also exposes a raw-data variant so the two
can be compared and the reconciliation step proven to matter.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.discrepancy_investigation import investigate_discrepancies, reconciled_amount
from src.models import Dataset


@dataclass
class ProfitabilityRow:
    key: str  # customer_id, product_id, or "local"/"international"
    label: str
    revenue: float
    direct_cost: float
    margin: float
    margin_pct: float


def _rows_from_invoices(dataset: Dataset, invoices, group_fn, label_fn) -> list:
    contracts_by_id = {c.contract_id: c for c in dataset.contracts}
    revenue_by_key = {}
    cost_by_key = {}

    for inv in invoices:
        contract = contracts_by_id.get(inv.contract_id)
        if contract is None:
            continue  # orphaned invoices can't be attributed to any customer/product
        key = group_fn(contract)
        revenue_by_key[key] = revenue_by_key.get(key, 0.0) + inv.amount
        cost_by_key[key] = cost_by_key.get(key, 0.0) + inv.direct_cost

    rows = []
    for key in sorted(revenue_by_key):
        revenue = round(revenue_by_key[key], 2)
        cost = round(cost_by_key[key], 2)
        margin = round(revenue - cost, 2)
        margin_pct = round(margin / revenue, 4) if revenue else 0.0
        rows.append(ProfitabilityRow(key=key, label=label_fn(key), revenue=revenue,
                                      direct_cost=cost, margin=margin, margin_pct=margin_pct))
    return rows


def _reconciled_invoices(dataset: Dataset):
    flags = investigate_discrepancies(dataset)
    flags_by_invoice_id = {f.invoice_id: f for f in flags}
    result = []
    for inv in dataset.invoices:
        amt = reconciled_amount(inv, flags_by_invoice_id)
        if amt is None:
            continue
        result.append(inv)
    return result


def profitability_by_customer(dataset: Dataset, use_reconciled: bool = True) -> list:
    invoices = _reconciled_invoices(dataset) if use_reconciled else dataset.invoices
    customers_by_id = {c.customer_id: c for c in dataset.customers}
    return _rows_from_invoices(
        dataset, invoices,
        group_fn=lambda contract: contract.customer_id,
        label_fn=lambda key: customers_by_id[key].name if key in customers_by_id else key,
    )


def profitability_by_product(dataset: Dataset, use_reconciled: bool = True) -> list:
    invoices = _reconciled_invoices(dataset) if use_reconciled else dataset.invoices
    products_by_id = {p.product_id: p for p in dataset.products}
    return _rows_from_invoices(
        dataset, invoices,
        group_fn=lambda contract: contract.product_id,
        label_fn=lambda key: products_by_id[key].name if key in products_by_id else key,
    )


def profitability_local_vs_international(dataset: Dataset, use_reconciled: bool = True) -> list:
    """'International' = customer's country differs from the contracting entity's country."""
    invoices = _reconciled_invoices(dataset) if use_reconciled else dataset.invoices
    customers_by_id = {c.customer_id: c for c in dataset.customers}

    def group_fn(contract):
        customer = customers_by_id[contract.customer_id]
        return "international" if customer.country != contract.contracting_entity_country else "local"

    return _rows_from_invoices(dataset, invoices, group_fn=group_fn,
                                label_fn=lambda key: key.capitalize())
