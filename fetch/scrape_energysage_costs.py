"""
Scrape solar installation cost data per state from EnergySage.

Output CSV columns:
  state, avg_system_cost_usd, avg_cost_per_watt_usd, avg_25yr_savings_usd
"""
import csv
import os
import re
import sys

from playwright.sync_api import sync_playwright

URL = "https://www.energysage.com/local-data/solar-panel-cost/#how-much-do-solar-panels-cost-in-your-state"


def _parse_usd(text: str) -> float | None:
    """Extract the first dollar value from a string, e.g. '$29,881' → 29881.0"""
    m = re.search(r"\$([0-9,]+(?:\.\d+)?)", text)
    return float(m.group(1).replace(",", "")) if m else None


def scrape() -> list[dict]:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ))
        page = ctx.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=45_000)
        page.wait_for_timeout(5_000)

        rows = []

        # Table 1 is the state table: State | Avg system cost | Avg $/W | Avg 25-yr savings
        tables = page.query_selector_all("table")
        state_table = None
        for table in tables:
            headers = [th.inner_text().strip() for th in table.query_selector_all("thead th")]
            if any("State" in h for h in headers):
                state_table = table
                break

        if state_table is None:
            ctx.close()
            browser.close()
            return []

        for tr in state_table.query_selector_all("tbody tr"):
            cells = tr.query_selector_all("td")
            if len(cells) < 4:
                continue
            state = cells[0].inner_text().strip()
            system_cost = _parse_usd(cells[1].inner_text())
            cost_per_watt = _parse_usd(cells[2].inner_text())
            savings_25yr = _parse_usd(cells[3].inner_text())
            if state and system_cost is not None:
                rows.append({
                    "state": state,
                    "avg_system_cost_usd": system_cost,
                    "avg_cost_per_watt_usd": cost_per_watt,
                    "avg_25yr_savings_usd": savings_25yr,
                })

        ctx.close()
        browser.close()
        return rows


def main():
    out_path = "data/solar_cost_by_state.csv"
    rows = scrape()

    if not rows:
        print("ERROR: no data extracted", file=sys.stderr)
        sys.exit(1)

    os.makedirs("data", exist_ok=True)
    fields = ["state", "avg_system_cost_usd", "avg_cost_per_watt_usd", "avg_25yr_savings_usd"]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows → {out_path}")
    print(f"{'State':<22} {'Sys Cost':>12} {'$/W':>8} {'25yr Savings':>14}")
    print("-" * 60)
    for r in rows:
        print(f"{r['state']:<22} ${r['avg_system_cost_usd']:>10,.0f} "
              f"${r['avg_cost_per_watt_usd']:>6.2f} "
              f"${r['avg_25yr_savings_usd']:>12,.0f}")


if __name__ == "__main__":
    main()
