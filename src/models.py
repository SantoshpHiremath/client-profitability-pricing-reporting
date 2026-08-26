"""Domain model for the fleet-leasing-shaped synthetic dataset.

Field choices are deliberately close to what a fleet-leasing Finance team
actually tracks (monthly recurring rate vs. one-off fees, contract start/end,
pricing-measure tagging) rather than a generic invoice/customer toy model.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Customer:
    customer_id: str
    name: str
    country: str  # ISO country code of the customer


@dataclass
class Product:
    product_id: str
    name: str
    category: str


@dataclass
class Contract:
    contract_id: str
    customer_id: str
    product_id: str
    contracting_entity_country: str  # ISO country code of the Arval-side entity
    monthly_rate: float
    start_date: date
    end_date: Optional[date]  # None = still active
    pricing_measure_id: Optional[str] = None  # set if a pricing measure applies

    @property
    def is_international(self) -> bool:
        """True when the customer and contracting entity sit in different countries."""
        return False  # overridden by dataset-level logic; see profitability.py


@dataclass
class Invoice:
    invoice_id: str
    contract_id: str
    month: date  # first-of-month marker for the billing period
    amount: float
    direct_cost: float  # cost directly attributable to servicing this invoice
    is_duplicate_of: Optional[str] = None  # set only in deliberately-injected duplicates


@dataclass
class PricingMeasure:
    measure_id: str
    description: str
    effective_date: date
    affected_contract_ids: list = field(default_factory=list)


@dataclass
class Dataset:
    customers: list  # list[Customer]
    products: list  # list[Product]
    contracts: list  # list[Contract]
    invoices: list  # list[Invoice]
    pricing_measures: list  # list[PricingMeasure]
