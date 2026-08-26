"""End-to-end demo: generate data, run discrepancy investigation, profitability
report, and pricing-effect report, and print all three like a Finance team's
ad-hoc report request would expect.
"""
from src.generate_data import generate_dataset
from src.reports import build_full_report


def money(x):
    return f"EUR {x:,.2f}"


def pct(x):
    return f"{x*100:.1f}%" if x is not None else "n/a"


def main():
    dataset = generate_dataset(seed=42)
    report = build_full_report(dataset)

    print("=" * 78)
    print("DISCREPANCY INVESTIGATION")
    print("=" * 78)
    print(f"{len(report.discrepancy_flags)} discrepancies found across "
          f"{len(dataset.invoices)} invoices.\n")
    by_cause = {}
    for f in report.discrepancy_flags:
        by_cause.setdefault(f.root_cause, []).append(f)
    for cause, flags in sorted(by_cause.items()):
        print(f"  {cause}: {len(flags)}")
        for f in flags[:3]:
            print(f"    {f.invoice_id} (contract {f.contract_id}, {f.month}): "
                  f"expected {money(f.expected_amount)}, actual {money(f.actual_amount)}, "
                  f"delta {money(f.delta)} ({pct(f.delta_pct)})")
        if len(flags) > 3:
            print(f"    ... and {len(flags) - 3} more")
    print()

    print("=" * 78)
    print("PROFITABILITY REPORT (reconciled data)")
    print("=" * 78)
    p = report.profitability
    print(f"Total revenue: {money(p.total_revenue)}   Total margin: {money(p.total_margin)}\n")

    print("By customer:")
    for row in p.by_customer:
        print(f"  {row.label:<32} revenue {money(row.revenue):>14}  margin {money(row.margin):>14}  ({pct(row.margin_pct)})")

    print("\nBy product:")
    for row in p.by_product:
        print(f"  {row.label:<32} revenue {money(row.revenue):>14}  margin {money(row.margin):>14}  ({pct(row.margin_pct)})")

    print("\nLocal vs. international:")
    for row in p.local_vs_international:
        print(f"  {row.label:<32} revenue {money(row.revenue):>14}  margin {money(row.margin):>14}  ({pct(row.margin_pct)})")
    print()

    print("=" * 78)
    print("PRICING-MEASURE EFFECT REPORT (observational -- see caveat below)")
    print("=" * 78)
    for r in report.pricing_effects:
        print(f"\n{r.measure_id}: {r.description} (effective {r.effective_date})")
        if r.insufficient_data:
            print("  Insufficient data to measure an effect (no affected contracts, or no "
                  "before/after invoice history).")
            continue
        print(f"  Affected contracts: {r.affected_contract_count}")
        print(f"  Avg monthly revenue/contract before: {money(r.avg_monthly_revenue_before)}")
        print(f"  Avg monthly revenue/contract after:  {money(r.avg_monthly_revenue_after)}")
        print(f"  Change: {pct(r.pct_change)}")
        print(f"  Retention as of last month in data: {r.retained_contract_count}/{r.affected_contract_count} ({pct(r.retention_rate)})")

    print("\nNote: this is an observational before/after comparison on the affected "
          "contracts only, not a randomized experiment -- it cannot rule out other "
          "factors that changed at the same time. See pricing-ab-test-analysis for "
          "a controlled-experiment approach where that distinction matters most.")


if __name__ == "__main__":
    main()
