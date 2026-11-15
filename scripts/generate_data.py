"""
Generate a realistic, fully synthetic retail-pharmacy supply chain dataset.

The simulation runs a weekly replenishment loop for every store x SKU:

    demand ~ Poisson(base * store_factor * seasonality)
    forecast = expected demand * category bias * noise
    order    = max(0, target_stock - on_hand)       (order-up-to policy)
    receipts = last week's order * DC fill rate     (DC-specific, can degrade)
    sales    = min(demand, on_hand + receipts)

Problems are deliberately planted so the analysis has something real to find:

  1. The Dallas DC's fill rate drops sharply in weeks 14-21 (a carrier issue).
  2. Cough & Cold is systematically under-forecast during the winter peak.
  3. A subset of stores runs with safety-stock parameters that are too low.

No real company data is used. Run:  python scripts/generate_data.py
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_STORES = 40
N_WEEKS = 26
START = date(2025, 9, 1)  # Monday

CATEGORIES = {
    # category: (n_skus, unit_cost range, seasonal amplitude, winter forecast bias)
    "Cough & Cold": (18, (4, 14), 0.85, -0.32),
    "Pain Relief": (16, (3, 12), 0.10, 0.00),
    "Vitamins": (16, (6, 25), 0.05, 0.04),
    "Allergy": (12, (5, 18), -0.45, 0.00),
    "Digestive Health": (14, (3, 11), 0.05, 0.00),
    "First Aid": (12, (2, 9), 0.00, 0.02),
    "Personal Care": (16, (2, 10), 0.00, -0.02),
    "Baby Care": (12, (6, 30), 0.00, 0.00),
}

DCS = [
    ("DC01", "Dallas DC", "TX"),
    ("DC02", "Atlanta DC", "GA"),
    ("DC03", "Phoenix DC", "AZ"),
]
REGIONS = {"DC01": "South Central", "DC02": "Southeast", "DC03": "Southwest"}
CITIES = {
    "DC01": ["Dallas", "Irving", "Plano", "Fort Worth", "Austin", "Houston", "Waco", "Tyler"],
    "DC02": ["Atlanta", "Marietta", "Savannah", "Augusta", "Macon", "Athens", "Columbus"],
    "DC03": ["Phoenix", "Chandler", "Tempe", "Mesa", "Tucson", "Scottsdale", "Gilbert"],
}


def build_dimensions(rng: np.random.Generator):
    dcs = pd.DataFrame(DCS, columns=["dc_id", "dc_name", "dc_state"])

    stores = []
    for i in range(N_STORES):
        dc_id = DCS[i % 3][0]
        city = rng.choice(CITIES[dc_id])
        fmt = rng.choice(["Urban", "Suburban", "Rural"], p=[0.3, 0.5, 0.2])
        stores.append(
            {
                "store_id": f"S{1001 + i}",
                "store_name": f"{city} #{1001 + i}",
                "city": city,
                "region": REGIONS[dc_id],
                "store_format": fmt,
                "dc_id": dc_id,
                "open_date": (date(2008, 1, 1) + timedelta(days=int(rng.integers(0, 5000)))).isoformat(),
            }
        )
    stores = pd.DataFrame(stores)

    products = []
    n = 0
    for cat, (k, (lo, hi), _, _) in CATEGORIES.items():
        for j in range(k):
            n += 1
            cost = round(float(rng.uniform(lo, hi)), 2)
            products.append(
                {
                    "sku": f"SKU{10000 + n}",
                    "product_name": f"{cat} Item {j + 1:02d}",
                    "category": cat,
                    "brand_type": rng.choice(["National", "Store Brand"], p=[0.6, 0.4]),
                    "unit_cost": cost,
                    "unit_price": round(cost * float(rng.uniform(1.6, 2.4)), 2),
                    "case_pack": int(rng.choice([6, 12, 24])),
                }
            )
    products = pd.DataFrame(products)
    return dcs, stores, products


def seasonality(week_idx: np.ndarray, amp: float) -> np.ndarray:
    # Peak around week 18 (early January)
    return 1 + amp * np.exp(-((week_idx - 18) ** 2) / (2 * 4.0**2)) - amp * 0.15


def simulate(rng, dcs, stores, products) -> tuple[pd.DataFrame, pd.DataFrame]:
    S, P, W = len(stores), len(products), N_WEEKS
    weeks = np.arange(W)

    store_factor = rng.lognormal(0, 0.35, S)
    store_factor *= np.where(stores.store_format == "Urban", 1.3, np.where(stores.store_format == "Rural", 0.7, 1.0))
    sku_base = rng.lognormal(np.log(6), 0.6, P)

    cat_params = products.category.map(lambda c: CATEGORIES[c])
    amp = np.array([c[2] for c in cat_params])
    winter_bias = np.array([c[3] for c in cat_params])

    # Planted issue 3: ~20% of stores with an under-sized safety stock
    low_ss_store = rng.random(S) < 0.2
    safety_weeks = np.where(low_ss_store, 0.0, 0.45)[:, None] * np.ones((1, P))

    # Planted issue 1: Dallas DC fill rate degrades in weeks 14-21
    dc_idx = stores.dc_id.map({d: i for i, d in enumerate(dcs.dc_id)}).to_numpy()
    fill_rate = np.full((3, W), 0.97)
    fill_rate[1] = 0.96
    fill_rate[2] = 0.975
    fill_rate[0, 14:22] = [0.86, 0.74, 0.66, 0.62, 0.65, 0.72, 0.80, 0.89]

    on_hand = np.round(sku_base[None, :] * store_factor[:, None] * 2.0)
    pipeline_order = np.round(sku_base[None, :] * store_factor[:, None])

    rows, ship_rows = [], []
    for w in weeks:
        season = np.stack([seasonality(np.array([w]), a)[0] for a in amp])
        expected = store_factor[:, None] * sku_base[None, :] * season[None, :]
        demand = rng.poisson(expected)

        winter = 1.0 if 13 <= w <= 22 else 0.0
        bias = 1 + winter_bias * winter + 0.01
        forecast = np.maximum(0, np.round(expected * bias[None, :] * rng.lognormal(0, 0.24, (S, P)), 1))

        fr = fill_rate[dc_idx, w][:, None]
        shipped = np.round(pipeline_order * np.clip(fr + rng.normal(0, 0.02, (S, P)), 0, 1))
        late = (rng.random((S, P)) < (1 - fr) * 0.8).astype(int)

        begin = on_hand
        available = begin + shipped
        sales = np.minimum(demand, available)
        lost = demand - sales
        end = available - sales

        # Order-up-to: cover ~1.5 weeks of forecast demand + safety stock
        target = forecast * (1.5 + safety_weeks)
        order = np.maximum(0, np.ceil(target - end))

        week_start = START + timedelta(weeks=int(w))
        for s in range(S):
            rows.append(
                pd.DataFrame(
                    {
                        "week_start": week_start.isoformat(),
                        "store_id": stores.store_id.iat[s],
                        "sku": products.sku.to_numpy(),
                        "begin_on_hand": begin[s].astype(int),
                        "receipts": shipped[s].astype(int),
                        "demand_units": demand[s].astype(int),
                        "sales_units": sales[s].astype(int),
                        "lost_sales_units": lost[s].astype(int),
                        "end_on_hand": end[s].astype(int),
                        "forecast_units": forecast[s],
                        "order_units": order[s].astype(int),
                        "safety_stock_weeks": safety_weeks[s],
                    }
                )
            )
            ship_rows.append(
                pd.DataFrame(
                    {
                        "week_start": week_start.isoformat(),
                        "dc_id": stores.dc_id.iat[s],
                        "store_id": stores.store_id.iat[s],
                        "sku": products.sku.to_numpy(),
                        "ordered_units": pipeline_order[s].astype(int),
                        "shipped_units": shipped[s].astype(int),
                        "days_late": late[s] * rng.integers(1, 5, P),
                    }
                )
            )
        on_hand, pipeline_order = end, order

    inv = pd.concat(rows, ignore_index=True)
    ship = pd.concat(ship_rows, ignore_index=True)
    return inv, ship


def main(out: Path) -> None:
    rng = np.random.default_rng(SEED)
    out.mkdir(parents=True, exist_ok=True)
    dcs, stores, products = build_dimensions(rng)
    inv, ship = simulate(rng, dcs, stores, products)

    # A little real-world mess for the staging layer to clean up
    messy = inv.sample(frac=0.002, random_state=SEED).index
    inv.loc[messy, "forecast_units"] = np.nan
    stores["store_name"] = stores["store_name"].str.upper().where(rng.random(len(stores)) < 0.3, stores["store_name"])

    dcs.to_csv(out / "distribution_centers.csv", index=False)
    stores.to_csv(out / "stores.csv", index=False)
    products.to_csv(out / "products.csv", index=False)
    inv.to_csv(out / "inventory_weekly.csv", index=False)
    ship.to_csv(out / "dc_shipments.csv", index=False)
    print(f"stores={len(stores)} skus={len(products)} weeks={N_WEEKS} inventory_rows={len(inv):,} shipment_rows={len(ship):,}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "raw")
    main(ap.parse_args().out)
