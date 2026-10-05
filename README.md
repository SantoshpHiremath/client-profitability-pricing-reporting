# Client & Product Profitability + Pricing-Effect Reporting

A tested Python project that reproduces two core Finance-team tasks: (1) local/international
profitability-KPI reporting by customer and product, and (2) evaluating the effect of pricing
measures over time. It starts from a discrepancy-investigation angle, building on my earlier
work as first point of contact for cross-department data-discrepancy investigations across
linked systems (Oracle Service Contracts + SharePoint). This project asks the same question
of contract, invoice, and pricing data: "do these two systems agree, and if not, why, and how
much does it distort the numbers management is looking at?"

## What it does

- Cross-checks every invoice against what its contract should have billed, and classifies
  each mismatch by root cause.
- Computes profitability KPIs by customer and product from the reconciled invoice data.
- Measures the effect of each pricing measure over time on the contracts it applies to.
- Assembles the results into the ad-hoc reports a Finance team typically requests.

## Data

The dataset (`src/generate_data.py`) is synthetic, seeded, fleet-leasing-shaped data that I
built myself: contracts, monthly invoices, and a pricing-measure log, with realistic problems
deliberately injected:

- a contract whose invoiced amount drifts from its contracted rate (a rebate applied on one
  system but not reflected on the other, the same shape of discrepancy I investigated
  before);
- a contract cancelled mid-month with a pro-rated final invoice;
- a customer or product renamed partway through the dataset, which would silently split one
  entity into two rows in a naive report.

The pipeline is built so real contract and invoice sources can replace the synthetic data.

## What it models

- **`src/models.py`**: `Contract`, `Invoice`, `PricingMeasure`, `Customer`, `Product`
  dataclasses shaped around what a fleet-leasing Finance team tracks: monthly recurring rate,
  one-off fees, contract start/end, the specific pricing measure (and effective date)
  applied to a contract, if any.

- **`src/discrepancy_investigation.py`**: cross-checks each invoice against what its contract
  should have billed that month (contracted monthly rate, pro-rated for partial months),
  flags mismatches above a materiality threshold, and classifies each mismatch into one of a
  small set of root causes (rebate/discount not reflected in contract record, pro-ration
  arithmetic error, duplicate invoice line, orphaned invoice with no matching contract)
  rather than just reporting "numbers don't match." This is a cross-system reconciliation:
  contracts and invoices are joined explicitly by `contract_id`, with unmatched invoices
  surfaced rather than silently dropped (the same cross-grain-join discipline as
  `staffing-analytics-kpi-engine`'s cost-per-hire projector).

- **`src/profitability.py`**: profitability KPIs by customer and by product (revenue, direct
  cost, margin, margin %), computed from the reconciled invoice data (after the discrepancy
  pass) rather than the raw invoice feed, plus a local vs. international split (customer
  country vs. contracting entity country). A test confirms that reconciled-vs-raw
  profitability can differ, so the reconciliation step demonstrably matters.

- **`src/pricing_effect.py`**: measures the effect of a pricing measure over time. For every
  pricing measure in the log, it computes a before/after comparison on the affected contracts
  only (average monthly revenue per contract, and retention: did the contract still exist N
  months later), against a naive baseline of "just compare overall revenue before and after
  the date," which can be misleading when contract mix changes around the same time. This
  follows the same "don't just eyeball an aggregate" discipline as `pricing-ab-test-analysis`,
  adapted to an observational (non-experimental) pricing-measure setting with no control
  group, so the report states that it measures before/after differences rather than
  causality.

- **`src/reports.py`**: assembles the two ad-hoc stakeholder reports: a profitability summary
  (by customer, by product, local vs. international) and a pricing-measure effect summary,
  both as plain dataclasses that render cleanly to a table (see `run_demo.py`).

- **`src/generate_data.py`**: seeded synthetic data generator (`mulberry32`-style
  deterministic PRNG) producing 40 contracts across 12 customers and 6 products, ~9 months of
  invoices each, 4 pricing measures, with the injected discrepancies listed above.

## Tests

31 tests (`pytest tests/ -v`), covering:

- Discrepancy detection: a clean matching invoice produces no flag; an unreflected-rebate
  invoice is flagged and classified correctly; a pro-rated final month matches exactly
  (regression test for bug #1); a duplicate invoice line is flagged; an orphaned invoice (no
  matching contract) is surfaced, not dropped or crashed on.
- Profitability: revenue/cost/margin arithmetic is correct per customer and per product; the
  local vs. international split sums back to the total; profitability computed from
  reconciled data differs from profitability computed from raw data on the fixture that
  contains a rebate discrepancy (the reconciliation step changes the answer).
- Pricing effect: before/after averages are computed correctly on a hand-built fixture with a
  known answer; only tagged contracts are included (regression test for bug #2); a pricing
  measure with zero affected contracts returns a clearly-marked "insufficient data" result
  instead of dividing by zero or silently returning 0.0.
- Data generation: deterministic given the same seed; every invoice's `contract_id` refers to
  a contract that exists in the dataset except the one deliberately-orphaned invoice.

## Running it

```bash
pip install -r requirements.txt
python3 run_demo.py       # discrepancy report + profitability report + pricing-effect report
pytest tests/ -v            # 31 tests
```

## Notes

Two bugs found and fixed during development, each now covered by a regression test:

1. **Pro-ration off-by-one.** The first version of the expected-invoice calculation pro-rated
   a contract's final partial month using `days_in_month` from the invoice month but the
   contract's end day from a different month in a leap-year edge case, producing an expected
   amount very slightly off from the correct pro-rated figure and flagging every final-month
   invoice as a false-positive discrepancy. Fixed by deriving both the days-elapsed and
   days-in-month from the same `calendar.monthrange()` call anchored to the invoice's own
   month. Caught by `test_prorated_final_month_matches_exactly`, which failed before the fix
   and passes after.

2. **Pricing-effect baseline included contracts unaffected by the measure.** The first
   version of `pricing_effect.py` computed "average revenue before/after" over all contracts
   active in the window instead of only the contracts the pricing measure applied to, which
   diluted the measured effect toward zero. Fixed by filtering to `contract_id`s tagged with
   that `measure_id` before computing the comparison. Caught by
   `test_effect_only_measures_affected_contracts`, which constructs a scenario where an
   untagged contract's revenue moves in the opposite direction and confirms it does not
   change the reported effect.

The project works on synthetic data and does not connect to a real leasing, ERP, or
accounting system. The pricing-effect analysis is observational, so it reports before/after
differences on the affected population. pandas/Python provides the structured tabular
analysis here.

## Possible extensions

- Connect to a real contract/invoice source (ERP or data warehouse export).
- Add a difference-in-differences comparison where a comparable control group exists.
- Export the reports to Excel or a BI dashboard.
