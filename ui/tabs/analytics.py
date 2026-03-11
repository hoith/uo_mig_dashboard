# ui/tabs/analytics.py
"""
Analytics tab: Performance Attribution, Factor Exposure, Liquidity Analysis.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from data.fetchers import fetch_price_data, fetch_sector_info, fetch_volume_data
from calculations.attribution import (
    SECTOR_ETF_MAP,
    calculate_bhb_attribution,
    get_benchmark_sector_weights,
)
from calculations.factors import fetch_ff_factors, run_factor_regression


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_THEME = dict(
    template="plotly_dark",
    font=dict(family="JetBrains Mono, monospace", color="#E0E0E0", size=11),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=20, r=20, t=40, b=20),
)
_YELLOW = "#FEE123"
_GREEN = "#00C805"
_RED = "#FF4444"
_ORANGE = "#FF8800"
_BLUE = "#4488FF"
_GRAY = "#666666"
_GRID = "#1a1a1a"


def _fmt_pct(v, decimals=2):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v * 100:.{decimals}f}%"


def _fmt_dollar(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"${v:,.0f}"


def _color_effect(v):
    if isinstance(v, str):
        return ""
    if np.isnan(v):
        return ""
    return f"color: {'#00C805' if v >= 0 else '#FF4444'}"


# ---------------------------------------------------------------------------
# Section 1 – Performance Attribution (BHB)
# ---------------------------------------------------------------------------

def _render_attribution(
    position_metrics: pd.DataFrame,
    prices_df: pd.DataFrame,
    benchmark: str,
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
    start_date,
    end_date,
):
    st.markdown("### Performance Attribution (Brinson-Hood-Beebower)")
    st.caption(
        "Decomposes active return into **Allocation** (sector weights), "
        "**Selection** (stock picking within sectors), and **Interaction** effects."
    )

    if position_metrics is None or position_metrics.empty:
        st.warning("No position data available.")
        return

    # Date range controls
    idx = portfolio_returns.index if not portfolio_returns.empty else pd.Index([])
    min_dt = idx.min().date() if len(idx) else start_date
    max_dt = idx.max().date() if len(idx) else end_date

    col_a, col_b = st.columns(2)
    with col_a:
        attr_start = st.date_input(
            "Attribution start", value=min_dt,
            min_value=min_dt, max_value=max_dt, key="attr_start"
        )
    with col_b:
        attr_end = st.date_input(
            "Attribution end", value=max_dt,
            min_value=min_dt, max_value=max_dt, key="attr_end"
        )

    if st.button("Run Attribution Analysis", key="run_attribution"):
        with st.spinner("Fetching sector classifications and ETF prices…"):
            current_syms = position_metrics["Symbol"].tolist()
            sector_map = fetch_sector_info(current_syms)

            etf_syms = list(SECTOR_ETF_MAP.values())
            sector_etf_prices = fetch_price_data(etf_syms, attr_start, attr_end)

        bench_weights = get_benchmark_sector_weights(benchmark)

        with st.spinner("Computing attribution…"):
            attr_df = calculate_bhb_attribution(
                position_metrics=position_metrics,
                prices_df=prices_df,
                sector_map=sector_map,
                sector_etf_prices=sector_etf_prices,
                benchmark_sector_weights=bench_weights,
                start_date=attr_start,
                end_date=attr_end,
            )

        if attr_df.empty:
            st.warning(
                "Attribution could not be computed. "
                "Ensure sector ETF price data is available for the selected period."
            )
            return

        data_rows = attr_df[attr_df["Sector"] != "TOTAL"]
        total_row = attr_df[attr_df["Sector"] == "TOTAL"].iloc[0]

        # ── KPI summary ───────────────────────────────────────────────────
        total_active = float(total_row["Total Effect"])
        total_alloc = float(total_row["Allocation Effect"])
        total_sel = float(total_row["Selection Effect"])
        total_inter = float(total_row["Interaction Effect"])

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Active Return", _fmt_pct(total_active),
                  help="Sum of all sector effects")
        k2.metric("Allocation Effect", _fmt_pct(total_alloc),
                  help="From over/underweighting sectors")
        k3.metric("Selection Effect", _fmt_pct(total_sel),
                  help="From stock picking within sectors")
        k4.metric("Interaction Effect", _fmt_pct(total_inter),
                  help="Combined weight + selection effect")

        # ── Stacked bar chart ─────────────────────────────────────────────
        fig = go.Figure()
        for label, col, color in [
            ("Allocation", "Allocation Effect", _BLUE),
            ("Selection", "Selection Effect", _GREEN),
            ("Interaction", "Interaction Effect", _ORANGE),
        ]:
            fig.add_trace(go.Bar(
                name=label,
                x=data_rows["Sector"],
                y=data_rows[col] * 100,
                marker_color=color,
                hovertemplate=f"<b>%{{x}}</b><br>{label}: %{{y:.2f}}%<extra></extra>",
            ))

        fig.update_layout(
            **_THEME,
            barmode="relative",
            height=360,
            title=dict(text="Attribution by Sector (%)", font=dict(color=_YELLOW)),
            xaxis=dict(gridcolor=_GRID, title=""),
            yaxis=dict(gridcolor=_GRID, title="Effect (%)"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, use_container_width=True)

        # ── Attribution table ─────────────────────────────────────────────
        display = attr_df.copy()
        pct_cols = [
            "Port Weight", "Bench Weight", "Active Weight",
            "Port Return", "Bench Return",
            "Allocation Effect", "Selection Effect", "Interaction Effect", "Total Effect",
        ]
        for c in pct_cols:
            display[c] = display[c].apply(
                lambda v: _fmt_pct(v) if not (isinstance(v, float) and np.isnan(v)) else "—"
            )

        st.dataframe(
            display,
            hide_index=True,
            use_container_width=True,
        )

        # ── Sector map legend ─────────────────────────────────────────────
        with st.expander("Sector classification details"):
            sec_tbl = (
                pd.DataFrame(
                    [(s, sector_map.get(s, "Unknown")) for s in current_syms
                     if s != "CASH"],
                    columns=["Symbol", "Sector"],
                )
            )
            st.dataframe(sec_tbl, hide_index=True, use_container_width=True)


# ---------------------------------------------------------------------------
# Section 2 – Factor Exposure (Fama-French)
# ---------------------------------------------------------------------------

_FACTOR_DESC = {
    "Mkt-RF": "Market — Excess market return (systematic risk)",
    "SMB": "Size — Small-cap premium (small minus big)",
    "HML": "Value — Book-to-market premium (high minus low)",
    "RMW": "Profitability — Operating profitability (robust minus weak)",
    "CMA": "Investment — Asset growth (conservative minus aggressive)",
}


def _render_factor_exposure(
    portfolio_returns: pd.Series,
    start_date,
    end_date,
):
    st.markdown("### Factor Exposure (Fama-French)")
    st.caption(
        "OLS regression of portfolio excess returns on Fama-French factors. "
        "Explains how much of portfolio return is explained by systematic risk premia."
    )

    if portfolio_returns.empty:
        st.warning("No portfolio return data available.")
        return

    idx = portfolio_returns.index
    min_dt = idx.min().date()
    max_dt = idx.max().date()

    col_a, col_b, col_c = st.columns([1, 1, 1])
    with col_a:
        ff_start = st.date_input(
            "Start date", value=min_dt,
            min_value=min_dt, max_value=max_dt, key="ff_start"
        )
    with col_b:
        ff_end = st.date_input(
            "End date", value=max_dt,
            min_value=min_dt, max_value=max_dt, key="ff_end"
        )
    with col_c:
        model_choice = st.radio(
            "Factor model", ["FF5", "FF3"],
            index=0, horizontal=True, key="ff_model"
        )

    if st.button("Run Factor Regression", key="run_factors"):
        with st.spinner("Downloading Fama-French factors from Ken French's data library…"):
            factors_df = fetch_ff_factors(
                str(ff_start), str(ff_end)
            )

        if factors_df.empty:
            st.error(
                "Could not download Fama-French factors. "
                "Check your internet connection or try a different date range."
            )
            return

        port_slice = portfolio_returns.loc[
            (portfolio_returns.index >= pd.to_datetime(ff_start)) &
            (portfolio_returns.index <= pd.to_datetime(ff_end))
        ]

        with st.spinner("Running regression…"):
            result = run_factor_regression(port_slice, factors_df, model=model_choice)

        if not result:
            st.warning(
                "Regression failed — insufficient overlapping observations "
                "(need at least 30 trading days)."
            )
            return

        # ── KPI row ───────────────────────────────────────────────────────
        alpha_ann = result["alpha"]
        r2 = result["r_squared"]
        adj_r2 = result["adj_r_squared"]
        n_sig = sum(1 for p in result["p_values"].values() if p < 0.05)
        n_factors = len(result["betas"])

        k1, k2, k3, k4 = st.columns(4)
        k1.metric(
            "Annualised Alpha",
            _fmt_pct(alpha_ann),
            f"t = {result['alpha_tstat']:.2f}",
            delta_color="normal" if alpha_ann >= 0 else "inverse",
        )
        k2.metric("R²", f"{r2:.3f}", f"Adj R² {adj_r2:.3f}")
        k3.metric(
            "Significant Factors",
            f"{n_sig} / {n_factors}",
            "at p < 0.05",
        )
        k4.metric("Observations", str(result["n_obs"]))

        # ── Factor loading chart ──────────────────────────────────────────
        factors_ordered = list(result["betas"].keys())
        betas_vals = [result["betas"][f] for f in factors_ordered]
        se_vals = [result["se"][f] for f in factors_ordered]
        p_vals = [result["p_values"][f] for f in factors_ordered]
        colors = [
            (_GREEN if b >= 0 else _RED)
            if p < 0.05 else _GRAY
            for b, p in zip(betas_vals, p_vals)
        ]

        fig_betas = go.Figure()
        # Error bars at ±1.96 SE (95% CI)
        fig_betas.add_trace(go.Bar(
            x=factors_ordered,
            y=betas_vals,
            marker_color=colors,
            error_y=dict(
                type="data",
                array=[1.96 * s for s in se_vals],
                visible=True,
                color="#888",
            ),
            hovertemplate=(
                "<b>%{x}</b><br>Beta: %{y:.3f}<extra></extra>"
            ),
        ))
        fig_betas.add_hline(y=0, line_dash="dot", line_color=_GRAY)
        fig_betas.update_layout(
            **_THEME,
            height=300,
            title=dict(
                text=f"{model_choice} Factor Loadings (± 1.96 SE, green/red = significant at 5%)",
                font=dict(color=_YELLOW),
            ),
            xaxis=dict(gridcolor=_GRID),
            yaxis=dict(gridcolor=_GRID, title="Beta"),
            showlegend=False,
        )
        st.plotly_chart(fig_betas, use_container_width=True)

        # ── Factor regression table ───────────────────────────────────────
        tbl_rows = []
        for f in factors_ordered:
            tbl_rows.append({
                "Factor": f,
                "Description": _FACTOR_DESC.get(f, ""),
                "Beta": f"{result['betas'][f]:.3f}",
                "T-Stat": f"{result['t_stats'][f]:.2f}",
                "P-Value": f"{result['p_values'][f]:.3f}",
                "Sig.": "✓" if result["p_values"][f] < 0.05 else "",
                "Contribution (ann.)": _fmt_pct(result["factor_contributions"][f]),
                "Factor Return (ann.)": _fmt_pct(result["factor_annual_means"][f]),
            })

        # Add alpha row at top
        tbl_rows.insert(0, {
            "Factor": "Alpha",
            "Description": "Unexplained excess return (manager skill / luck)",
            "Beta": "—",
            "T-Stat": f"{result['alpha_tstat']:.2f}",
            "P-Value": f"{result['alpha_pvalue']:.3f}",
            "Sig.": "✓" if result["alpha_pvalue"] < 0.05 else "",
            "Contribution (ann.)": _fmt_pct(alpha_ann),
            "Factor Return (ann.)": "—",
        })

        st.dataframe(
            pd.DataFrame(tbl_rows),
            hide_index=True,
            use_container_width=True,
        )

        # ── Cumulative actual vs model-predicted chart ────────────────────
        aligned = result["aligned_returns"]
        rf_daily = aligned["RF"]
        factor_cols = [c for c in aligned.columns if c not in ("portfolio", "RF")]

        betas_arr = np.array([result["alpha_daily"]] + [result["betas"][f] for f in factor_cols])
        X_pred = np.column_stack([
            np.ones(len(aligned)),
            aligned[factor_cols].values
        ])
        predicted_excess = X_pred @ betas_arr
        predicted_returns = predicted_excess + rf_daily.values

        cum_actual = (1 + aligned["portfolio"]).cumprod()
        cum_model = (1 + pd.Series(predicted_returns, index=aligned.index)).cumprod()

        fig_cum = go.Figure()
        fig_cum.add_trace(go.Scatter(
            x=cum_actual.index, y=(cum_actual - 1) * 100,
            name="Actual Portfolio",
            line=dict(color=_YELLOW, width=2),
        ))
        fig_cum.add_trace(go.Scatter(
            x=cum_model.index, y=(cum_model - 1) * 100,
            name=f"{model_choice} Model",
            line=dict(color=_BLUE, width=1.5, dash="dash"),
        ))
        fig_cum.update_layout(
            **_THEME,
            height=300,
            title=dict(
                text="Cumulative Return: Actual vs Factor Model (%)",
                font=dict(color=_YELLOW),
            ),
            xaxis=dict(gridcolor=_GRID),
            yaxis=dict(gridcolor=_GRID, title="Cumulative Return (%)"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig_cum, use_container_width=True)


# ---------------------------------------------------------------------------
# Section 3 – Liquidity / ADV Analysis
# ---------------------------------------------------------------------------

def _render_liquidity(position_metrics: pd.DataFrame):
    st.markdown("### Liquidity / ADV Analysis")
    st.caption(
        "Estimates exit risk using 90-day average daily volume (ADV). "
        "Days to liquidate = Position Shares ÷ (ADV × Participation Rate)."
    )

    if position_metrics is None or position_metrics.empty:
        st.warning("No position data available.")
        return

    pm_sec = position_metrics[position_metrics["Symbol"] != "CASH"].copy()
    if pm_sec.empty:
        st.info("No tradeable positions.")
        return

    col_a, col_b = st.columns([2, 1])
    with col_a:
        participation = st.slider(
            "Participation rate (% of ADV per day)",
            min_value=5, max_value=30, value=20, step=5, key="liq_part"
        ) / 100.0
    with col_b:
        st.markdown("")
        st.markdown("")
        run_liq = st.button("Refresh Volume Data", key="run_liquidity")

    # Fetch volume on initial load or when button pressed
    syms = pm_sec["Symbol"].tolist()

    @st.cache_data(ttl=3600, show_spinner=False)
    def _cached_vol(syms_tuple):
        return fetch_volume_data(list(syms_tuple), period="3mo")

    with st.spinner("Fetching 90-day volume data…"):
        vol_df = _cached_vol(tuple(syms))

    if vol_df.empty:
        st.warning("Could not fetch volume data. Displaying positions without liquidity metrics.")
        return

    # Calculate 90-day ADV (shares) and derived metrics
    rows = []
    for _, row in pm_sec.iterrows():
        sym = row["Symbol"]
        qty = float(row.get("Quantity", 0))
        price = float(row.get("Current Price", 0))
        mkt_val = float(row.get("Market Value", qty * price))
        weight = float(row.get("Weight", 0))

        if sym in vol_df.columns:
            adv_shares = float(vol_df[sym].dropna().mean())
        else:
            adv_shares = np.nan

        adv_value = adv_shares * price if not np.isnan(adv_shares) and price > 0 else np.nan

        if not np.isnan(adv_shares) and adv_shares > 0 and qty > 0:
            days_to_liq = qty / (adv_shares * participation)
        else:
            days_to_liq = np.nan

        pos_adv_ratio = (mkt_val / adv_value) if (adv_value and adv_value > 0) else np.nan

        if np.isnan(days_to_liq):
            flag = "N/A"
        elif days_to_liq < 5:
            flag = "Low"
        elif days_to_liq <= 20:
            flag = "Medium"
        else:
            flag = "High"

        rows.append({
            "Symbol": sym,
            "Position ($)": mkt_val,
            "Weight (%)": weight,
            "ADV Shares": adv_shares,
            "ADV Value ($)": adv_value,
            "Position / ADV": pos_adv_ratio,
            "Days to Liquidate": days_to_liq,
            "Liquidity Risk": flag,
        })

    liq_df = pd.DataFrame(rows).sort_values("Days to Liquidate", na_position="last")

    # ── KPI row ───────────────────────────────────────────────────────────
    high_risk = liq_df[liq_df["Liquidity Risk"] == "High"]
    med_risk = liq_df[liq_df["Liquidity Risk"] == "Medium"]
    avg_days = liq_df["Days to Liquidate"].dropna().mean()
    worst_days = liq_df["Days to Liquidate"].dropna().max()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("High Risk Positions", str(len(high_risk)),
              "Days to liquidate > 20")
    k2.metric("Medium Risk Positions", str(len(med_risk)),
              "5–20 days to liquidate")
    k3.metric("Avg Days to Liquidate",
              f"{avg_days:.1f}" if not np.isnan(avg_days) else "—")
    k4.metric("Worst Position",
              f"{worst_days:.1f} days" if not np.isnan(worst_days) else "—")

    # ── Horizontal bar chart ──────────────────────────────────────────────
    chart_df = liq_df.dropna(subset=["Days to Liquidate"]).copy()
    if not chart_df.empty:
        bar_colors = [
            _RED if r == "High" else (_ORANGE if r == "Medium" else _GREEN)
            for r in chart_df["Liquidity Risk"]
        ]
        fig_liq = go.Figure(go.Bar(
            x=chart_df["Days to Liquidate"],
            y=chart_df["Symbol"],
            orientation="h",
            marker_color=bar_colors,
            hovertemplate=(
                "<b>%{y}</b><br>Days: %{x:.1f}<extra></extra>"
            ),
        ))
        fig_liq.add_vline(
            x=5, line_dash="dot", line_color=_GREEN,
            annotation_text="5d", annotation_font_color=_GREEN,
        )
        fig_liq.add_vline(
            x=20, line_dash="dot", line_color=_ORANGE,
            annotation_text="20d", annotation_font_color=_ORANGE,
        )
        fig_liq.update_layout(
            **_THEME,
            height=max(250, len(chart_df) * 28 + 80),
            title=dict(
                text=f"Days to Liquidate at {participation:.0%} ADV Participation",
                font=dict(color=_YELLOW),
            ),
            xaxis=dict(gridcolor=_GRID, title="Trading Days"),
            yaxis=dict(gridcolor=_GRID, autorange="reversed"),
            showlegend=False,
        )
        st.plotly_chart(fig_liq, use_container_width=True)

    # ── Liquidity table ───────────────────────────────────────────────────
    display = liq_df.copy()
    display["Position ($)"] = display["Position ($)"].apply(_fmt_dollar)
    display["Weight (%)"] = display["Weight (%)"].apply(
        lambda v: f"{v:.1f}%" if not np.isnan(v) else "—"
    )
    display["ADV Shares"] = display["ADV Shares"].apply(
        lambda v: f"{v:,.0f}" if not np.isnan(v) else "—"
    )
    display["ADV Value ($)"] = display["ADV Value ($)"].apply(_fmt_dollar)
    display["Position / ADV"] = display["Position / ADV"].apply(
        lambda v: f"{v:.2f}x" if not np.isnan(v) else "—"
    )
    display["Days to Liquidate"] = display["Days to Liquidate"].apply(
        lambda v: f"{v:.1f}" if not np.isnan(v) else "—"
    )

    st.dataframe(display, hide_index=True, use_container_width=True)

    st.caption(
        f"**Methodology:** 90-day average daily volume × {participation:.0%} participation rate. "
        "Risk flags: 🟢 Low < 5 days · 🟡 Medium 5–20 days · 🔴 High > 20 days."
    )


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------

def render_analytics_tab(
    portfolio_returns: pd.Series,
    portfolio_df: pd.DataFrame,
    prices_df: pd.DataFrame,
    position_metrics: pd.DataFrame,
    benchmark_returns: pd.Series,
    benchmark: str,
    metrics: dict,
    total_value: float,
    risk_free_rate: float,
    start_date=None,
    end_date=None,
):
    """Render the Analytics tab (Attribution · Factor Exposure · Liquidity)."""
    st.markdown("## Analytics")

    tab_attr, tab_factors, tab_liq = st.tabs([
        "Performance Attribution",
        "Factor Exposure",
        "Liquidity / ADV",
    ])

    with tab_attr:
        _render_attribution(
            position_metrics=position_metrics,
            prices_df=prices_df,
            benchmark=benchmark,
            portfolio_returns=portfolio_returns,
            benchmark_returns=benchmark_returns,
            start_date=start_date,
            end_date=end_date,
        )

    with tab_factors:
        _render_factor_exposure(
            portfolio_returns=portfolio_returns,
            start_date=start_date,
            end_date=end_date,
        )

    with tab_liq:
        _render_liquidity(position_metrics=position_metrics)
