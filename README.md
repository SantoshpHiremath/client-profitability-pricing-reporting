# Client & Product Profitability + Pricing-Effect Reporting

A real, tested Python project built specifically for Arval Deutschland's
"Werkstudent Pricing" posting (Finance team, Oberhaching): it reproduces
the two things the JD names as the actual daily job — (1) local/
international profitability-KPI reporting by customer and product, and
(2) evaluating the effect of pricing measures over time — and it deliberately
starts from a **discrepancy-investigation** angle, because that is the one
piece of this I have real prior work experience in, not just a coding
exercise: at UL Solutions I was the first point of contact for
cross-department data-discrepancy investigations across linked systems
(Oracle Service Contracts + SharePoint). This project asks the same
question — "do these two systems agree, and if not, why, and how much
does it distort the numbers management is looking at?" — of contract,
invoice, and pricing data instead.

## What this is (read before citing anywhere)

**There is no real Arval, BNP Paribas, or leasing-industry data here.**
The dataset (`src/generate_data.py`) is synthetic, seeded, fleet-leasing-
shaped data I built myself: contracts, monthly invoices, and a pricing-
measure log, with deliberately injected realistic problems (a contract
whose invoiced amount silently drifts from its contracted rate — a rebate
applied on one system but not reflected on the other, exactly the shape of
discrepancy I investigated at UL Solutions; a contract cancelled mid-month
with a pro-rated final invoice; a customer or product renamed partway
through the dataset, which would silently split one entity into two rows
in a naive report). I have no real leasing, fleet-management, or Arval
data or domain access. I'm also not from a Business/Finance/
Wirtschaftsingenieurwesen/Mathematik background — I'm an AI Master's
student — which the JD explicitly says is fine to apply anyway with, and
I've tried to make this project honest evidence rather than a way to
paper over that gap.

## What this models

- **`src/models.py`** — `Contract`, `Invoice`, `PricingMeasure`,
  `Customer`, `Product` dataclasses shaped around what a fleet-leasing
  Finance team actually tracks: monthly recurring rate, one-off fees,
  contract start/end, the specific pricing measure (and effective date)
  applied to a contract, if any.

- **`src/discrepancy_investigation.py`** — the UL-Solutions-shaped part:
  cross-checks each invoice against what its contract *should* have
  billed that month (contracted monthly rate, pro-rated for partial
  months), flags mismatches above a materiality threshold, and
  classifies each mismatch into one of a small set of real root causes
  (rebate/discount not reflected in contract record, pro-ration
  arithmetic error, duplicate invoice line, orphaned invoice with no
  matching contract) rather than just reporting "numbers don't match."
  This is a genuine cross-system reconciliation, not a single-table
  computation — contracts and invoices are joined explicitly by
  `contract_id`, with unmatched invoices surfaced rather than silently
  dropped (the same cross-grain-join discipline as
  `staffing-analytics-kpi-engine`'s cost-per-hire projector).

- **`src/profitability.py`** — the JD's core ask: profitability KPIs by
  customer and by product — revenue, direct cost, margin, margin % —
  computed from the *reconciled* invoice data (i.e., after the
  discrepancy pass), not the raw, possibly-wrong invoice feed, plus a
  local vs. international split (customer country vs. contracting
  entity country). Includes a check that reconciled-vs-raw profitability
  can genuinely differ, so the reconciliation step is proven to matter
  and isn't just decorative.

- **`src/pricing_effect.py`** — the JD's second core ask: measuring the
  effect of a pricing measure over time. For every pricing measure in the
  log, computes a real before/after comparison on the affected contracts
  only (average monthly revenue per contract, and retention — did the
  contract still exist N months later), against a naive baseline of
  "just compare overall revenue before and after the date," which this
  project shows can be misleading when contract mix changes around the
  same time — the same "don't just eyeball an aggregate" discipline as
  `pricing-ab-test-analysis`'s statistical approach, adapted to an
  observational (non-experimental) pricing-measure setting where there's
  no control group, so the report is explicit about that limitation
  rather than implying causality it can't support.

- **`src/reports.py`** — assembles the two ad-hoc stakeholder reports a
  Finance team would actually request: a profitability summary
  (by customer, by product, local vs. international) and a pricing-
  measure effect summary, both as plain dataclasses that render cleanly
  to a table (see `run_demo.py`).

- **`src/generate_data.py`** — seeded synthetic data generator
  (`mulberry32`-style deterministic PRNG) producing 40 contracts across
  12 customers and 6 products, ~9 months of invoices each, 4 pricing
  measures, with the specific injected discrepancies listed above.

## Real bugs found and fixed during development

1. **Pro-ration off-by-one.** The first version of the expected-invoice
   calculation pro-rated a contract's final partial month using
   `days_in_month` from the invoice month but the *contract's* end day
   from a different month in a leap-year edge case, producing a expected
   amount very slightly off from the correct pro-rated figure and
   flagging every single final-month invoice as a false-positive
   discrepancy. Fixed by deriving both the days-elapsed and days-in-month
   from the same `calendar.monthrange()` call anchored to the invoice's
   own month. Caught by `test_prorated_final_month_matches_exactly`,
   which failed before the fix (flagged a real invoice as discrepant)
   and passes after.

2. **Pricing-effect baseline included contracts unaffected by the
   measure.** The first version of `pricing_effect.py` computed "average
   revenue before/after" over *all* contracts active in the window
   instead of only the contracts the pricing measure actually applied
   to, which diluted the measured effect toward zero and would have
   under-reported a real pricing change's impact. Fixed by filtering to
   `contract_id`s explicitly tagged with that `measure_id` before
   computing the before/after comparison. Caught by
   `test_effect_only_measures_affected_contracts`, which constructs a
   scenario where an untagged contract's revenue moves in the opposite
   direction and confirms it does not change the reported effect.

## Verification

31 tests (`pytest tests/ -v`), covering:

- Discrepancy detection: a clean matching invoice produces no flag; an
  unreflected-rebate invoice is flagged and classified correctly; a
  pro-rated final month matches exactly (regression test for bug #1); a
  duplicate invoice line is flagged; an orphaned invoice (no matching
  contract) is surfaced, not dropped or crashed on.
- Profitability: revenue/cost/margin arithmetic is correct per customer
  and per product; local vs. international split sums back to the total;
  profitability computed from reconciled data differs from profitability
  computed from raw data on the fixture that contains a rebate
  discrepancy (proving the reconciliation step changes the answer).
- Pricing effect: before/after averages are computed correctly on a hand-
  built fixture with a known answer; only tagged contracts are included
  (regression test for bug #2); a pricing measure with zero affected
  contracts returns a clearly-marked "insufficient data" result instead
  of dividing by zero or silently returning 0.0.
- Data generation: deterministic given the same seed; every invoice's
  `contract_id` refers to a contract that exists in the dataset except
  the one deliberately-orphaned invoice.

## Running it

```bash
pip install -r requirements.txt
python3 run_demo.py       # discrepancy report + profitability report + pricing-effect report
pytest tests/ -v            # 31 tests
```

## What this doesn't demonstrate

This project doesn't connect to any real leasing, ERP, or accounting
system, doesn't use SAS (I have no SAS experience — pandas/Python fills
the same "structured tabular analysis" role here, and I'd need to learn
SAS on the job if the role specifically requires it), and its pricing-
measure-effect analysis is observational, not a controlled experiment —
it explicitly reports that limitation rather than claiming causal proof.
It demonstrates the underlying discipline the JD's two core tasks need:
reconciling data across linked records before trusting a profitability
number (the same investigative habit as my UL Solutions work, applied to
a new domain), and measuring a pricing change's effect against the
correct comparison group rather than a misleading aggregate — built and
verified on synthetic data I could construct and check myself.
