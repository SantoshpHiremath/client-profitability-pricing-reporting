"""Deterministic synthetic data generator for fleet-leasing-shaped data.

Uses a small seeded PRNG (mulberry32-style) so the dataset is identical on
every run given the same seed -- important for reproducible tests and for
the "run it yourself and check" verification discipline this campaign
follows throughout.
"""
from __future__ import annotations

import calendar
from datetime import date

from src.models import Customer, Product, Contract, Invoice, PricingMeasure, Dataset


def mulberry32(seed: int):
    state = seed & 0xFFFFFFFF

    def next_float() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & 0xFFFFFFFF
        t = state
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t = (t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    return next_float


def add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def days_in_month(d: date) -> int:
    return calendar.monthrange(d.year, d.month)[1]


CUSTOMER_NAMES = [
    ("Nordbau Logistik GmbH", "DE"), ("Alpine Fleet Services", "AT"),
    ("Rhein Transport AG", "DE"), ("Benelux Mobility BV", "NL"),
    ("Munich Field Sales GmbH", "DE"), ("Lyon Distribution SARL", "FR"),
    ("Berlin Facility Group", "DE"), ("Vienna Courier Co", "AT"),
    ("Frankfurt Consulting Fleet", "DE"), ("Milano Servizi Mobili", "IT"),
    ("Hamburg Health Logistics", "DE"), ("Zurich Field Ops AG", "CH"),
]

PRODUCT_NAMES = [
    ("Compact Sedan Lease", "passenger"), ("Executive Sedan Lease", "passenger"),
    ("Light Van Lease", "commercial"), ("Panel Van Lease", "commercial"),
    ("Electric Compact Lease", "passenger"), ("Pickup Truck Lease", "commercial"),
]

ENTITY_COUNTRIES = ["DE", "DE", "DE", "NL", "FR"]  # weighted toward DE contracting entity


def generate_dataset(seed: int = 42) -> Dataset:
    rnd = mulberry32(seed)

    customers = [Customer(f"CUST-{i+1:03d}", name, country) for i, (name, country) in enumerate(CUSTOMER_NAMES)]
    products = [Product(f"PROD-{i+1:03d}", name, category) for i, (name, category) in enumerate(PRODUCT_NAMES)]

    base_start = date(2025, 1, 1)
    contracts = []
    for i in range(40):
        cust = customers[int(rnd() * len(customers))]
        prod = products[int(rnd() * len(products))]
        entity_country = ENTITY_COUNTRIES[int(rnd() * len(ENTITY_COUNTRIES))]
        start = add_months(base_start, int(rnd() * 6))
        # ~25% of contracts end partway through the dataset window (pro-rated final month)
        end = add_months(start, 6 + int(rnd() * 6)) if rnd() < 0.25 else None
        base_rate = 250 + rnd() * 550  # 250-800 EUR/month
        contracts.append(Contract(
            contract_id=f"CTR-{i+1:04d}",
            customer_id=cust.customer_id,
            product_id=prod.product_id,
            contracting_entity_country=entity_country,
            monthly_rate=round(base_rate, 2),
            start_date=start,
            end_date=end,
        ))

    # Pricing measures: each tags a subset of contracts with an effective date and a % change.
    pricing_measures = [
        PricingMeasure("PM-001", "Fuel-surcharge adjustment +6%", date(2025, 4, 1), []),
        PricingMeasure("PM-002", "Loyalty discount -8% for renewing fleets", date(2025, 6, 1), []),
        PricingMeasure("PM-003", "Electric-vehicle incentive -10%", date(2025, 7, 1), []),
        PricingMeasure("PM-004", "Commercial-van rate increase +5%", date(2025, 9, 1), []),
    ]
    measure_effect = {"PM-001": 1.06, "PM-002": 0.92, "PM-003": 0.90, "PM-004": 1.05}

    for c in contracts:
        r = rnd()
        if c.product_id == "PROD-005" and r < 0.7:  # electric compact -> EV incentive
            c.pricing_measure_id = "PM-003"
        elif c.product_id in ("PROD-003", "PROD-004", "PROD-006") and r < 0.5:  # commercial -> van increase
            c.pricing_measure_id = "PM-004"
        elif r < 0.3:
            c.pricing_measure_id = "PM-001"
        elif r < 0.45:
            c.pricing_measure_id = "PM-002"

    for pm in pricing_measures:
        pm.affected_contract_ids = [c.contract_id for c in contracts if c.pricing_measure_id == pm.measure_id]

    # Invoices: one per contract per active month in the Jan-2025..Sep-2025 window.
    window_months = [add_months(date(2025, 1, 1), m) for m in range(9)]
    invoices = []
    invoice_counter = 1
    discrepancy_contract = contracts[2]   # will get an unreflected-rebate discrepancy
    duplicate_contract = contracts[5]     # will get a duplicate invoice line
    orphan_month = window_months[4]

    for c in contracts:
        for month in window_months:
            if month < c.start_date:
                continue
            if c.end_date and month > c.end_date:
                continue

            rate = c.monthly_rate
            if c.pricing_measure_id:
                pm = next(p for p in pricing_measures if p.measure_id == c.pricing_measure_id)
                if month >= pm.effective_date:
                    rate = round(rate * measure_effect[c.pricing_measure_id], 2)

            # Pro-rate the final month if the contract ends mid-month.
            amount = rate
            if c.end_date and c.end_date.year == month.year and c.end_date.month == month.month:
                dim = days_in_month(month)
                days_active = c.end_date.day
                amount = round(rate * days_active / dim, 2)

            # Inject: unreflected rebate on discrepancy_contract from month index 3 onward --
            # invoice bills 12% less than contract rate would suggest, simulating a rebate
            # applied in the billing system but never written back to the contract record.
            if c.contract_id == discrepancy_contract.contract_id and month >= window_months[3]:
                amount = round(amount * 0.88, 2)

            direct_cost = round(amount * (0.55 + rnd() * 0.15), 2)

            invoices.append(Invoice(
                invoice_id=f"INV-{invoice_counter:05d}",
                contract_id=c.contract_id,
                month=month,
                amount=amount,
                direct_cost=direct_cost,
            ))
            invoice_counter += 1

            # Inject: one duplicate invoice line for duplicate_contract in one specific month.
            if c.contract_id == duplicate_contract.contract_id and month == window_months[2]:
                dup_id = f"INV-{invoice_counter:05d}"
                invoices.append(Invoice(
                    invoice_id=dup_id,
                    contract_id=c.contract_id,
                    month=month,
                    amount=amount,
                    direct_cost=direct_cost,
                    is_duplicate_of=invoices[-1].invoice_id,
                ))
                invoice_counter += 1

    # Inject: one orphaned invoice with no matching contract (a data-entry error / deleted contract).
    invoices.append(Invoice(
        invoice_id=f"INV-{invoice_counter:05d}",
        contract_id="CTR-9999",
        month=orphan_month,
        amount=412.50,
        direct_cost=260.00,
    ))

    return Dataset(customers=customers, products=products, contracts=contracts,
                    invoices=invoices, pricing_measures=pricing_measures)
