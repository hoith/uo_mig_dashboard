# calculations/attribution.py
"""
Brinson-Hood-Beebower (BHB) performance attribution.

Decomposes active return vs. a benchmark into:
  Allocation Effect  – did we over/underweight the right sectors?
  Selection Effect   – did we pick better stocks within each sector?
  Interaction Effect – combined over/underweight + stock selection
"""

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Sector ETF proxies for benchmark sector returns
# ---------------------------------------------------------------------------

SECTOR_ETF_MAP: dict[str, str] = {
    "Technology": "XLK",
    "Financials": "XLF",
    "Energy": "XLE",
    "Health Care": "XLV",
    "Industrials": "XLI",
    "Consumer Discretionary": "XLY",
    "Communication Services": "XLC",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
    "Consumer Staples": "XLP",
    "Materials": "XLB",
}

# Approximate GICS sector weights for SPY (S&P 500) as of 2025-2026
SPY_SECTOR_WEIGHTS: dict[str, float] = {
    "Technology": 0.32,
    "Financials": 0.13,
    "Health Care": 0.12,
    "Consumer Discretionary": 0.11,
    "Communication Services": 0.09,
    "Industrials": 0.08,
    "Consumer Staples": 0.06,
    "Energy": 0.04,
    "Materials": 0.02,
    "Real Estate": 0.02,
    "Utilities": 0.02,
}

# Approximate GICS sector weights for IEMG (EM equity) as of 2025-2026
IEMG_SECTOR_WEIGHTS: dict[str, float] = {
    "Technology": 0.28,
    "Financials": 0.22,
    "Consumer Discretionary": 0.14,
    "Communication Services": 0.10,
    "Materials": 0.08,
    "Industrials": 0.06,
    "Energy": 0.05,
    "Consumer Staples": 0.04,
    "Health Care": 0.02,
    "Utilities": 0.01,
    "Real Estate": 0.01,
}


def get_benchmark_sector_weights(benchmark: str) -> dict[str, float]:
    """Return sector weight dict appropriate for the selected benchmark.

    IEMG  → EM sector weights.
    All others → S&P 500 sector weights.
    """
    if benchmark == "IEMG":
        return IEMG_SECTOR_WEIGHTS
    return SPY_SECTOR_WEIGHTS


# ---------------------------------------------------------------------------
# Core attribution engine
# ---------------------------------------------------------------------------

def calculate_bhb_attribution(
    position_metrics: pd.DataFrame,
    prices_df: pd.DataFrame,
    sector_map: dict,
    sector_etf_prices: pd.DataFrame,
    benchmark_sector_weights: dict,
    start_date,
    end_date,
) -> pd.DataFrame:
    """Brinson-Hood-Beebower attribution analysis.

    Parameters
    ----------
    position_metrics : pd.DataFrame
        Current position table with columns Symbol, Weight, Quantity.
    prices_df : pd.DataFrame
        Historical prices for portfolio holdings.
    sector_map : dict
        {symbol: sector} from ``fetch_sector_info``.
    sector_etf_prices : pd.DataFrame
        Prices of SPDR sector ETFs (XLK, XLF, …) for the same period.
    benchmark_sector_weights : dict
        {sector: weight} for the chosen benchmark.
    start_date, end_date : date-like
        Period over which to compute attribution.

    Returns
    -------
    pd.DataFrame
        One row per sector plus a TOTAL summary row.
        Columns: Sector, Port Weight, Bench Weight, Active Weight,
                 Port Return, Bench Return,
                 Allocation Effect, Selection Effect, Interaction Effect, Total Effect.
        All weight/return/effect columns are in decimal form.
    """
    if position_metrics is None or position_metrics.empty:
        return pd.DataFrame()

    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)

    # ── Portfolio sector weights ─────────────────────────────────────────────
    pm = position_metrics.copy()
    pm["Sector"] = pm["Symbol"].map(sector_map).fillna("Unknown")
    pm_sec = pm[~pm["Symbol"].isin(["CASH", "Cash"])].copy()

    if pm_sec.empty:
        return pd.DataFrame()

    total_sec_weight = pm_sec["Weight"].sum()
    if total_sec_weight <= 0:
        return pd.DataFrame()

    sector_port_weights = (
        pm_sec.groupby("Sector")["Weight"].sum() / total_sec_weight
    )

    # ── Portfolio sector returns (period total return, weight-averaged) ──────
    sector_port_returns: dict[str, float] = {}

    for sector, grp in pm_sec.groupby("Sector"):
        sym_weights = grp.set_index("Symbol")["Weight"]
        syms = [s for s in sym_weights.index if s in prices_df.columns]
        if not syms:
            continue

        sliced = prices_df[syms].loc[
            (prices_df.index >= start) & (prices_df.index <= end)
        ]
        if len(sliced) < 2:
            continue

        sym_rets = {}
        for s in syms:
            col = sliced[s].dropna()
            if len(col) >= 2:
                sym_rets[s] = float(col.iloc[-1] / col.iloc[0] - 1)

        if not sym_rets:
            continue

        total_w = sum(float(sym_weights.get(s, 0)) for s in sym_rets)
        if total_w > 0:
            sector_port_returns[sector] = sum(
                sym_rets[s] * float(sym_weights.get(s, 0)) for s in sym_rets
            ) / total_w

    # ── Benchmark sector returns from sector ETF prices ──────────────────────
    sector_bench_returns: dict[str, float] = {}

    if not sector_etf_prices.empty:
        for sector, etf in SECTOR_ETF_MAP.items():
            if etf not in sector_etf_prices.columns:
                continue
            col = sector_etf_prices[etf].dropna()
            col = col.loc[(col.index >= start) & (col.index <= end)]
            if len(col) >= 2:
                sector_bench_returns[sector] = float(col.iloc[-1] / col.iloc[0] - 1)

    # ── Total benchmark return (weighted average of benchmark sectors) ────────
    total_bench_num = sum(
        benchmark_sector_weights.get(s, 0) * r
        for s, r in sector_bench_returns.items()
    )
    total_bench_den = sum(
        benchmark_sector_weights.get(s, 0)
        for s in sector_bench_returns
    )
    R_b = total_bench_num / total_bench_den if total_bench_den > 0 else 0.0

    # ── BHB decomposition ────────────────────────────────────────────────────
    all_sectors = sorted(
        (set(sector_port_weights.index) | set(benchmark_sector_weights.keys()))
        - {"Unknown", "Cash"}
    )

    rows: list[dict] = []
    for sector in all_sectors:
        w_p = float(sector_port_weights.get(sector, 0.0))
        w_b = float(benchmark_sector_weights.get(sector, 0.0))
        r_p = sector_port_returns.get(sector, np.nan)
        r_b = sector_bench_returns.get(sector, np.nan)

        allocation = (w_p - w_b) * (r_b - R_b) if not np.isnan(r_b) else 0.0
        selection = w_b * (r_p - r_b) if not (np.isnan(r_p) or np.isnan(r_b)) else 0.0
        interaction = (w_p - w_b) * (r_p - r_b) if not (np.isnan(r_p) or np.isnan(r_b)) else 0.0

        rows.append(
            {
                "Sector": sector,
                "Port Weight": w_p,
                "Bench Weight": w_b,
                "Active Weight": w_p - w_b,
                "Port Return": r_p,
                "Bench Return": r_b,
                "Allocation Effect": allocation,
                "Selection Effect": selection,
                "Interaction Effect": interaction,
                "Total Effect": allocation + selection + interaction,
            }
        )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # Totals row
    totals = {
        "Sector": "TOTAL",
        "Port Weight": df["Port Weight"].sum(),
        "Bench Weight": df["Bench Weight"].sum(),
        "Active Weight": df["Active Weight"].sum(),
        "Port Return": np.nan,
        "Bench Return": np.nan,
        "Allocation Effect": df["Allocation Effect"].sum(),
        "Selection Effect": df["Selection Effect"].sum(),
        "Interaction Effect": df["Interaction Effect"].sum(),
        "Total Effect": df["Total Effect"].sum(),
    }
    return pd.concat([df, pd.DataFrame([totals])], ignore_index=True)
