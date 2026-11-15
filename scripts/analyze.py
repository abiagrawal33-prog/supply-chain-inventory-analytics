"""
Read the dbt marts, produce the charts used in the README, and write an
auto-generated executive summary (docs/EXECUTIVE_SUMMARY.md).

Run after `dbt build`:  python scripts/analyze.py
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "warehouse" / "supply_chain.duckdb"
IMG = ROOT / "docs" / "images"

# Palette: validated categorical order (blue, orange, aqua) + neutral inks
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK_2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1", "#fcfcfb"

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK_2,
        "axes.titlecolor": INK,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": INK_2,
        "ytick.color": INK_2,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "lines.linewidth": 2,
        "savefig.dpi": 160,
        "savefig.bbox": "tight",
    }
)


def subtitle(ax, text):
    ax.text(0, 1.02, text, transform=ax.transAxes, color=INK_2, fontsize=9.5, va="bottom")


def save(fig, name):
    IMG.mkdir(parents=True, exist_ok=True)
    fig.savefig(IMG / name)
    plt.close(fig)


def main() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    df = lambda sql: con.sql(sql).df()

    # ---------- headline KPIs ----------
    k = df(
        """
        select 1 - sum(stockout_weeks) * 1.0 / sum(store_sku_weeks) as in_stock,
               sum(lost_sales_dollars) as lost, sum(sales_dollars) as sales
        from marts.mart_in_stock_weekly
        """
    ).iloc[0]
    fa = df(
        """
        select 1 - sum(wape * demand_units) / sum(demand_units) as acc,
               sum(bias * demand_units) / sum(demand_units)     as bias
        from marts.mart_forecast_accuracy
        """
    ).iloc[0]

    # ---------- 1. In-stock by DC ----------
    dc = df(
        """
        select week_start, m.dc_id, d.dc_name,
               1 - sum(stockout_weeks) * 1.0 / sum(store_sku_weeks) as in_stock
        from marts.mart_in_stock_weekly m
        join marts.dim_distribution_center d using (dc_id)
        group by all order by week_start
        """
    )
    fig, ax = plt.subplots(figsize=(10, 4.6))
    colors = {"DC01": ORANGE, "DC02": BLUE, "DC03": AQUA}
    ends = dc.groupby("dc_id").in_stock.last().sort_values()
    nudge = dict(zip(ends.index, [-7, 0, 7]))  # keep end labels from colliding
    for dc_id, g in dc.groupby("dc_id"):
        ax.plot(g.week_start, g.in_stock, color=colors[dc_id], label=g.dc_name.iat[0])
        ax.annotate(
            g.dc_name.iat[0], (g.week_start.iat[-1], g.in_stock.iat[-1]),
            xytext=(6, nudge[dc_id]), textcoords="offset points", va="center", color=INK_2, fontsize=9,
        )
    dal = dc[dc.dc_id == "DC01"].reset_index(drop=True)
    lo = dal.in_stock.idxmin()
    ax.axvspan(dal.week_start.iat[14], dal.week_start.iat[21], color=GRID, alpha=0.6, lw=0)
    ax.annotate(
        f"Dallas DC fill-rate issue\nin-stock fell to {dal.in_stock.iat[lo]:.1%}",
        (dal.week_start.iat[lo], dal.in_stock.iat[lo]), xytext=(-190, 10), textcoords="offset points",
        color=INK, fontsize=9, arrowprops=dict(arrowstyle="-", color=MUTED, lw=1),
    )
    ax.yaxis.set_major_locator(mtick.MultipleLocator(0.04))
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=0))
    ax.set_title("Weekly in-stock rate by distribution center", pad=22)
    subtitle(ax, "Share of store x SKU weeks with no lost sales. Shaded: Dallas DC carrier issue")
    ax.legend(frameon=False, loc="lower left", fontsize=9)
    ax.margins(x=0.01)
    ax.set_xlim(right=dal.week_start.iat[-1] + (dal.week_start.iat[1] - dal.week_start.iat[0]) * 3)
    save(fig, "01_in_stock_by_dc.png")

    # ---------- 2. Lost sales by root cause ----------
    rc = df(
        """
        select root_cause, count(*) as stockouts, sum(lost_sales_dollars) as lost
        from marts.mart_stockout_root_cause group by 1 order by lost
        """
    )
    fig, ax = plt.subplots(figsize=(10, 3.8))
    bars = ax.barh(rc.root_cause, rc.lost, color=BLUE, height=0.55)
    total = rc.lost.sum()
    for b, v, n in zip(bars, rc.lost, rc.stockouts):
        ax.text(v + total * 0.01, b.get_y() + b.get_height() / 2,
                f"${v/1000:,.0f}K  ({v/total:.0%}, {n:,} stockouts)", va="center", color=INK_2, fontsize=9)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f"${x/1000:,.0f}K"))
    ax.set_xlim(0, rc.lost.max() * 1.45)
    ax.set_title("Lost sales by primary stockout root cause", pad=22)
    subtitle(ax, "Every stockout classified by rule-based root-cause logic in dbt")
    save(fig, "02_root_cause.png")

    # ---------- 3. Forecast bias by category, winter vs rest ----------
    bias = df(
        """
        select category,
               sum(case when w.season = 'Winter' then bias * demand_units end)
                 / sum(case when w.season = 'Winter' then demand_units end) as winter_bias,
               sum(case when w.season <> 'Winter' then bias * demand_units end)
                 / sum(case when w.season <> 'Winter' then demand_units end) as other_bias
        from marts.mart_forecast_accuracy f join marts.dim_week w using (week_start)
        group by 1 order by winter_bias desc
        """
    )
    fig, ax = plt.subplots(figsize=(10, 4.4))
    y = range(len(bias))
    ax.barh([i + 0.2 for i in y], bias.other_bias, height=0.36, color=BLUE, label="Sep-Nov")
    ax.barh([i - 0.2 for i in y], bias.winter_bias, height=0.36, color=ORANGE, label="Dec-Feb")
    ax.set_yticks(list(y), bias.category)
    ax.axvline(0, color=INK_2, lw=1)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=0))
    cc = bias[bias.category == "Cough & Cold"].iloc[0]
    ax.annotate(f"{cc.winter_bias:.0%} under-forecast\nin the winter peak",
                (cc.winter_bias, list(bias.category).index("Cough & Cold") - 0.2),
                xytext=(25, 22), textcoords="offset points", va="center", fontsize=9, color=INK,
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=1))
    ax.set_title("Forecast bias by category", pad=22)
    subtitle(ax, "(forecast - demand) / demand. Negative = under-forecasting")
    ax.legend(frameon=False, loc="lower left")
    save(fig, "03_forecast_bias.png")

    # ---------- 4. Forecast accuracy depends on the level you measure ----------
    lvl = df(
        """
        with f as (
            select f.*, p.category from marts.fct_inventory_weekly f
            join marts.dim_product p using (sku) where not is_missing_forecast
        ),
        levels as (
            select 'Store x SKU x week' as level, store_id || sku || week_start as k, forecast_units, demand_units from f
            union all select 'DC x SKU x week', dc_id || sku || week_start, forecast_units, demand_units from f
            union all select 'Chain x SKU x week', sku || week_start, forecast_units, demand_units from f
            union all select 'Chain x category x week', category || week_start, forecast_units, demand_units from f
        ),
        agg as (
            select level, k, sum(forecast_units) as fc, sum(demand_units) as dm from levels group by 1, 2
        )
        select level, 1 - sum(abs(fc - dm)) / sum(dm) as acc from agg group by 1 order by acc
        """
    )
    fig, ax = plt.subplots(figsize=(10, 3.6))
    bars = ax.barh(lvl.level, lvl.acc, color=BLUE, height=0.55)
    for b, v in zip(bars, lvl.acc):
        ax.text(v + 0.01, b.get_y() + b.get_height() / 2, f"{v:.1%}", va="center", color=INK_2, fontsize=9)
    ax.set_xlim(0, 1.08)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=0))
    ax.set_title("Forecast accuracy (1 - WAPE) by aggregation level", pad=22)
    subtitle(ax, "Same forecast, very different scores: always state the level when reporting accuracy")
    save(fig, "04_forecast_accuracy_levels.png")

    # ---------- 5. Store scorecard ----------
    sc = df("select * from marts.mart_store_scorecard order by in_stock_rate")
    low = sc.avg_safety_stock_weeks < 0.1
    fig, ax = plt.subplots(figsize=(10, 4.2))
    x = list(range(len(sc)))
    for mask, color, label in [(low, ORANGE, "Safety stock set to 0 weeks"),
                               (~low, BLUE, "Standard safety stock (0.45 weeks)")]:
        xs = [i for i, m in zip(x, mask) if m]
        ax.vlines(xs, sc.in_stock_rate.min() - 0.01, sc.in_stock_rate[mask], color=GRID, lw=1, zorder=1)
        ax.scatter(xs, sc.in_stock_rate[mask], s=42, color=color, label=label, zorder=3,
                   edgecolors=SURFACE, linewidths=1.5)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=0))
    ax.set_xticks([])
    ax.set_xlabel("40 stores, sorted by in-stock rate")
    ax.legend(frameon=False, loc="lower right")
    ax.set_title("Store in-stock scorecard", pad=22)
    subtitle(ax, "The bottom stores share one thing: a misconfigured replenishment parameter")
    save(fig, "05_store_scorecard.png")

    # ---------- executive summary ----------
    dallas_lost = df(
        """select sum(lost_sales_dollars) from marts.mart_stockout_root_cause
           where root_cause = 'DC short-ship / late delivery'"""
    ).iat[0, 0]
    low_ss = sc[low]
    cc_share = df(
        """select avg(case when category = 'Cough & Cold' then 1.0 else 0 end)
           from marts.mart_stockout_root_cause where root_cause = 'Forecast under-call'"""
    ).iat[0, 0]
    cc_sku_share = df("select avg(case when category = 'Cough & Cold' then 1.0 else 0 end) from marts.dim_product").iat[0, 0]
    lines = [
        "# Executive summary",
        "",
        "_Auto-generated by `scripts/analyze.py` from the dbt marts. Synthetic data._",
        "",
        "| KPI | Value |",
        "|---|---|",
        f"| In-stock rate | **{k.in_stock:.1%}** |",
        f"| Lost sales | **${k.lost:,.0f}** ({k.lost / (k.sales + k.lost):.1%} of demand $) |",
        f"| Forecast accuracy (1 - WAPE, store x SKU x week) | **{fa.acc:.1%}** |",
        f"| Forecast bias | **{fa.bias:+.1%}** |",
        "",
        "## Root causes of lost sales",
        "",
        "| Root cause | Stockouts | Lost sales | Share |",
        "|---|---:|---:|---:|",
        *[f"| {r.root_cause} | {r.stockouts:,} | ${r.lost:,.0f} | {r.lost / total:.0%} |"
          for r in rc.sort_values("lost", ascending=False).itertuples()],
        "",
        "## Recommendations",
        "",
        f"1. **Fix the Cough & Cold winter forecast.** It ran {cc.winter_bias:.0%} biased in Dec-Feb "
        f"vs {cc.other_bias:+.0%} in the fall, and it drives {cc_share:.0%} of all forecast-driven stockouts "
        f"while being only {cc_sku_share:.0%} of SKUs. Add a seasonal index or a winter uplift to the model "
        "before the next cold season, and track bias weekly, not only accuracy.",
        f"2. **Escalate Dallas DC fill rate with the carrier.** DC short-ships cost ${dallas_lost:,.0f} "
        f"in lost sales; Dallas in-stock fell to {dal.in_stock.iat[lo]:.1%} at the low point. "
        "Add a fill-rate alert (< 90% for 2 weeks) to the ops dashboard.",
        f"3. **Reset safety stock at {len(low_ss)} stores.** They run with 0 weeks of safety stock and "
        f"average {low_ss.in_stock_rate.mean():.1%} in-stock vs {sc[~low].in_stock_rate.mean():.1%} elsewhere. "
        "This is a configuration fix with no added forecast work.",
        "",
    ]
    (ROOT / "docs" / "EXECUTIVE_SUMMARY.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
