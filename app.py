"""
Portfolio & Risk Management Dashboard
=====================================
A production-ready Streamlit dashboard for portfolio managers and valuation leads.
Features: Portfolio reconstruction, performance analytics, risk metrics (VaR/CVaR),
stress testing, rebalancing optimization, and Basel III-style reporting.

Run with: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# =============================================================================
# PAGE CONFIGURATION (MUST BE FIRST STREAMLIT CALL)
# =============================================================================

st.set_page_config(
    page_title="Portfolio Risk Dashboard",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# MODULE IMPORTS
# =============================================================================

from styles import CSS
from config import PORTFOLIO_CONFIG, IEMG_WEIGHTS, SPY_WEIGHTS, TICKER_COUNTRY_MAP
from state import initialize_session_state
from ui.layout import render_header, render_ticker_bar, render_footer
from ui.sidebar import render_sidebar
from ui.tabs.overview import render_overview_tab
from ui.tabs.positions import render_positions_tab
from ui.tabs.transactions import render_transactions_tab
from ui.tabs.risk import render_risk_tab
from ui.tabs.stress import render_stress_tab
from ui.tabs.reports import render_reports_tab

from data.fetchers import (fetch_price_data, fetch_iemg_weights,
                            fetch_spy_weights)
from calculations.cost_basis import (calculate_cost_basis_from_transactions,
                                      estimate_cost_basis_from_prices)
from calculations.portfolio import (reconstruct_portfolio_from_initial,
                                     calculate_returns)
from calculations.performance import (calculate_time_weighted_return,
                                       calculate_money_weighted_return,
                                       calculate_adjusted_benchmark,
                                       calculate_performance_metrics)
from calculations.positions import (calculate_position_metrics,
                                     calculate_exante_metrics)
from calculations.risk import calculate_var_cvar


# =============================================================================
# MAIN APPLICATION
# =============================================================================

def main():
    # Apply CSS
    st.markdown(CSS, unsafe_allow_html=True)

    # Initialize session state
    initialize_session_state()

    # Render sidebar and get parameters
    params = render_sidebar()
    start_date = params['start_date']
    end_date = params['end_date']
    benchmark = params['benchmark']
    var_confidence = params['var_confidence']
    enable_crp = params['enable_crp']
    position_limit = params['position_limit']
    risk_free_rate = params['risk_free_rate']

    selected_portfolio = st.session_state.selected_portfolio

    # Render header
    render_header()

    # ==========================================================================
    # LOAD DATA
    # ==========================================================================

    # Get symbols from BOTH holdings AND transactions (filter out any empty/null values)
    # CASH is handled specially - not fetched from Yahoo Finance
    holdings_symbols = [s for s in st.session_state.holdings['symbol'].unique().tolist()
                        if s and isinstance(s, str) and s.strip()]

    # Also get symbols from transactions (for stocks bought that aren't in initial holdings)
    transaction_symbols = []
    if st.session_state.transactions is not None and not st.session_state.transactions.empty:
        transaction_symbols = [s for s in st.session_state.transactions['symbol'].unique().tolist()
                               if s and isinstance(s, str) and s.strip()]

    # Combine and deduplicate
    all_symbols = list(set(holdings_symbols + transaction_symbols))

    # Separate cash from tradeable symbols
    cash_symbols = [s for s in all_symbols if s.upper() == 'CASH']
    tradeable_symbols = [s for s in all_symbols if s.upper() != 'CASH']
    symbols = all_symbols  # Keep full list for reference

    all_symbols = list(set(tradeable_symbols + [benchmark]))

    # Fetch price data
    with st.spinner("Loading market data..."):
        prices_df = fetch_price_data(all_symbols, start_date, end_date)

    # Filter symbols to only those with valid price data
    if not prices_df.empty:
        valid_symbols = [s for s in tradeable_symbols if s in prices_df.columns and prices_df[s].notna().any()]
        if len(valid_symbols) < len(tradeable_symbols):
            missing = set(tradeable_symbols) - set(valid_symbols)
            if missing:
                st.warning(f"Could not fetch price data for: {', '.join(missing)}")
        tradeable_symbols = valid_symbols

        # Add CASH as constant $1 price if present in holdings
        if cash_symbols:
            prices_df['CASH'] = 1.0

        # Combine tradeable symbols with cash
        symbols = tradeable_symbols + cash_symbols

    if prices_df.empty:
        st.error("Failed to load price data. Please check your internet connection and try again.")
        return

    # Estimate cost basis from prices if still zero
    if st.session_state.holdings['cost_basis'].sum() == 0:
        st.session_state.holdings = estimate_cost_basis_from_prices(
            st.session_state.holdings,
            prices_df[symbols] if symbols else prices_df
        )

    # Separate benchmark
    benchmark_prices = prices_df[benchmark] if benchmark in prices_df.columns else pd.Series()
    benchmark_returns = benchmark_prices.pct_change().dropna()

    # Get initial cash from session state
    initial_cash = st.session_state.get('initial_cash', 0.0)

    # Reconstruct portfolio using new function that properly tracks holdings through time
    portfolio_df, weights_df, cash_flows_df, current_holdings_df = reconstruct_portfolio_from_initial(
        st.session_state.transactions,
        st.session_state.holdings,
        prices_df[symbols],
        initial_cash
    )

    # Calculate Time-Weighted Returns (TWR)
    twr_metrics = calculate_time_weighted_return(portfolio_df, cash_flows_df)

    # Calculate Money-Weighted Returns (MWR/IRR)
    mwr_metrics = calculate_money_weighted_return(portfolio_df, cash_flows_df, initial_cash)

    # Calculate adjusted benchmark (accounts for same cash flows as portfolio)
    adjusted_benchmark = calculate_adjusted_benchmark(benchmark_prices, portfolio_df, cash_flows_df)

    # Calculate SIMPLE returns (WITH cash flow effects - what actually happened to portfolio value)
    simple_returns = calculate_returns(portfolio_df)  # Raw pct_change, includes CF impact

    # Calculate simple total/annualized return (includes cash flow effects)
    if not simple_returns.empty:
        simple_total = (1 + simple_returns).prod() - 1
        n_days_simple = len(simple_returns)
        n_years_simple = n_days_simple / 252 if n_days_simple > 0 else 1
        simple_annualized = (1 + simple_total) ** (1 / n_years_simple) - 1 if n_years_simple > 0 else simple_total
    else:
        simple_total = 0
        simple_annualized = 0

    # Get TWR-adjusted daily returns for Sharpe/Sortino calculations
    # These returns EXCLUDE the impact of external cash flows (pure investment performance)
    if 'daily_twr' in twr_metrics and not twr_metrics['daily_twr'].empty:
        # Convert cumulative TWR back to daily returns
        cumulative_twr = twr_metrics['daily_twr'] + 1  # Convert from return to growth factor
        twr_daily_returns = cumulative_twr.pct_change().dropna()
    else:
        twr_daily_returns = simple_returns

    # Keep portfolio_returns as alias for compatibility with rest of code
    portfolio_returns = twr_daily_returns

    # Calculate performance metrics using TWR-adjusted daily returns (for proper Sharpe, etc.)
    metrics = calculate_performance_metrics(portfolio_returns, benchmark_returns, risk_free_rate)

    # Add all return metrics
    # TWR = Time-Weighted Return (excludes cash flow timing, measures manager skill)
    metrics['twr_total'] = twr_metrics['twr_total']
    metrics['twr_annualized'] = twr_metrics['twr_annualized']

    # MWR = Money-Weighted Return (includes cash flow timing, measures investor experience)
    metrics['mwr_total'] = mwr_metrics['mwr_total']
    metrics['mwr_annualized'] = mwr_metrics['mwr_annualized']

    # Simple = Raw returns (includes cash flows as if they were gains/losses)
    metrics['simple_total'] = simple_total
    metrics['simple_annualized'] = simple_annualized

    # Benchmark returns - both raw and cash-flow adjusted
    # Total returns (not annualized)
    metrics['raw_benchmark_total'] = adjusted_benchmark['raw_total']  # Raw benchmark total return
    metrics['adjusted_benchmark_total'] = adjusted_benchmark['adjusted_total']  # Cash-flow adjusted total return
    # Annualized returns
    metrics['raw_benchmark_return'] = adjusted_benchmark['raw_annualized']  # Raw benchmark annualized
    metrics['adjusted_benchmark_return'] = adjusted_benchmark['adjusted_annualized']  # Cash-flow adjusted annualized
    metrics['benchmark_return'] = adjusted_benchmark['raw_annualized']  # For backward compatibility

    # Calculate Beta excluding cash (securities-only beta)
    if 'securities_value' in portfolio_df.columns and not benchmark_returns.empty:
        securities_values = portfolio_df['securities_value'].dropna()
        if len(securities_values) > 1:
            securities_returns = securities_values.pct_change().dropna()
            # Align with benchmark
            aligned_sec = pd.concat([securities_returns, benchmark_returns], axis=1, join='inner')
            if len(aligned_sec) > 10:
                aligned_sec.columns = ['securities', 'benchmark']
                cov_sec = np.cov(aligned_sec['securities'].values, aligned_sec['benchmark'].values)[0, 1]
                var_bench = aligned_sec['benchmark'].var()
                beta_ex_cash = cov_sec / var_bench if var_bench > 0 else 1
                metrics['beta_ex_cash'] = beta_ex_cash
            else:
                metrics['beta_ex_cash'] = metrics.get('beta', 1)
        else:
            metrics['beta_ex_cash'] = metrics.get('beta', 1)
    else:
        metrics['beta_ex_cash'] = metrics.get('beta', 1)

    # Calculate Current (trailing 90-day) beta — most recent market sensitivity
    _BETA_TRAILING_DAYS = 90
    if not portfolio_returns.empty and not benchmark_returns.empty:
        recent_port = portfolio_returns.iloc[-_BETA_TRAILING_DAYS:]
        aligned_recent = pd.concat([recent_port, benchmark_returns], axis=1, join='inner')
        aligned_recent.columns = ['portfolio', 'benchmark']
        if len(aligned_recent) >= 20:
            cov_recent = np.cov(aligned_recent['portfolio'].values, aligned_recent['benchmark'].values)[0, 1]
            var_recent = aligned_recent['benchmark'].var()
            metrics['beta_current_90d'] = cov_recent / var_recent if var_recent > 0 else 1.0
        else:
            metrics['beta_current_90d'] = metrics.get('beta_ex_cash', 1.0)
    else:
        metrics['beta_current_90d'] = metrics.get('beta_ex_cash', 1.0)

    # Update symbols list to include any new holdings from transactions (like LULU)
    current_symbols = current_holdings_df['symbol'].tolist() if not current_holdings_df.empty else symbols

    # Fetch any missing price data for new symbols
    missing_symbols = [s for s in current_symbols if s not in prices_df.columns and s.upper() != 'CASH']
    if missing_symbols:
        try:
            new_prices = fetch_price_data(missing_symbols, start_date, end_date)
            if not new_prices.empty:
                for col in new_prices.columns:
                    prices_df[col] = new_prices[col]
        except:
            pass  # Continue with available data

    # Calculate cost basis for current holdings from transactions
    if not current_holdings_df.empty:
        current_holdings_df = calculate_cost_basis_from_transactions(
            st.session_state.transactions,
            current_holdings_df
        )
        # For tickers without transactions, use start-of-range price as cost basis
        current_holdings_df = estimate_cost_basis_from_prices(
            current_holdings_df,
            prices_df
        )

    # Calculate position metrics using CURRENT holdings (after all transactions)
    position_metrics = calculate_position_metrics(
        current_holdings_df if not current_holdings_df.empty else st.session_state.holdings,
        prices_df,
        benchmark_returns
    )

    # Determine which benchmark constituent weights and passive ETF to use.
    # IEMG benchmark → use EM constituent weights, passive ETF = 'IEMG'
    # SPY benchmark  → use S&P 500 constituent weights (via IVV), passive ETF = 'IVV'
    # Other benchmarks → no constituent weights available; ex-ante TE not computed.
    _SUPPORTED_BENCH = {'IEMG', 'SPY'}
    if benchmark == 'IEMG':
        _weights_source = fetch_iemg_weights() if not position_metrics.empty else IEMG_WEIGHTS
        _passive_etf = 'IEMG'
    elif benchmark == 'SPY':
        _weights_source = fetch_spy_weights() if not position_metrics.empty else SPY_WEIGHTS
        _passive_etf = 'IVV'
    else:
        _weights_source = {}
        _passive_etf = None

    # Add Index Weight and Active Weight columns to positions table
    if not position_metrics.empty:
        position_metrics['Index Weight'] = position_metrics['Symbol'].map(
            lambda s: _weights_source.get(s, 0.0)
        )
        # Active weight = position's share of the non-passive (active) book.
        # Formula: active_weight_i = raw_weight_i / (100 - passive_etf_raw_weight)
        passive_portfolio_weight = (
            position_metrics.loc[position_metrics['Symbol'] == _passive_etf, 'Weight'].sum()
            if _passive_etf else 0.0
        )
        active_book_pct = 100.0 - passive_portfolio_weight
        if active_book_pct > 0 and _passive_etf:
            position_metrics['Active Weight'] = position_metrics.apply(
                lambda row: (row['Weight'] / active_book_pct * 100)
                            if row['Symbol'] not in (_passive_etf, 'CASH')
                            else 0.0,
                axis=1
            )
        else:
            position_metrics['Active Weight'] = 0.0

    # Calculate ex-ante (current composition) beta and tracking error.
    if benchmark in _SUPPORTED_BENCH and _passive_etf:
        exante = calculate_exante_metrics(
            position_metrics, prices_df,
            index_weights=_weights_source, passive_etf=_passive_etf,
            benchmark_returns=benchmark_returns
        )
    else:
        # Ex-ante beta valid for any benchmark — trailing 252-day individual betas
        # Ex-ante TE suppressed — no constituent weights for this benchmark
        exante = calculate_exante_metrics(
            position_metrics, prices_df,
            index_weights={}, passive_etf=None,
            benchmark_returns=benchmark_returns
        )

    # ==========================================================================
    # PRE-TAB METRICS (hoisted for ticker bar)
    # ==========================================================================
    total_value = position_metrics['Market Value'].sum() if not position_metrics.empty else 0
    total_cost = (position_metrics['Cost Basis'] * position_metrics['Quantity']).sum() if not position_metrics.empty else 0
    total_pnl = total_value - total_cost
    twr_total = metrics.get('twr_total', 0)
    adj_bench_total = metrics.get('adjusted_benchmark_total', 0)
    twr_ann = metrics.get('twr_annualized', 0)
    adj_bench_ann = metrics.get('adjusted_benchmark_return', 0)
    beta_ex_cash = metrics.get('beta_ex_cash', 1)

    # Compute current_symbols for stress/optimization (active non-cash positions only)
    active_current_symbols = [
        s for s in current_symbols
        if s.upper() != 'CASH' and s in prices_df.columns
    ]

    # Compute VaR metrics (needed for risk tab and reports tab)
    hist_var, hist_cvar = calculate_var_cvar(portfolio_returns, var_confidence, 'historical')
    param_var, param_cvar = calculate_var_cvar(portfolio_returns, var_confidence, 'parametric')

    # Render ticker bar
    render_ticker_bar(selected_portfolio, total_value, total_pnl, twr_total,
                      benchmark, adj_bench_total, beta_ex_cash)

    # ==========================================================================
    # MAIN TABS
    # ==========================================================================

    tabs = st.tabs([
        "OVERVIEW",
        "POSITIONS",
        "TRANSACTIONS",
        "RISK",
        "STRESS / REBALANCE",
        "REPORTS"
    ])

    with tabs[0]:
        render_overview_tab(
            metrics=metrics,
            portfolio_df=portfolio_df,
            benchmark_returns=benchmark_returns,
            position_metrics=position_metrics,
            benchmark=benchmark,
            adjusted_benchmark=adjusted_benchmark,
            total_value=total_value,
            total_cost=total_cost,
            portfolio_returns=portfolio_returns,
            twr_total=twr_total,
            mwr_total=metrics.get('mwr_total', 0)
        )

    with tabs[1]:
        render_positions_tab(
            position_metrics=position_metrics,
            position_limit=position_limit,
            enable_crp=enable_crp
        )

    with tabs[2]:
        render_transactions_tab()

    with tabs[3]:
        render_risk_tab(
            portfolio_returns=portfolio_returns,
            metrics=metrics,
            total_value=total_value,
            var_confidence=var_confidence,
            risk_free_rate=risk_free_rate,
            prices_df=prices_df,
            symbols=symbols,
            hist_var=hist_var,
            hist_cvar=hist_cvar,
            param_var=param_var,
            param_cvar=param_cvar,
            exante=exante
        )

    with tabs[4]:
        render_stress_tab(
            portfolio_returns=portfolio_returns,
            metrics=metrics,
            total_value=total_value,
            position_metrics=position_metrics,
            prices_df=prices_df,
            current_symbols=active_current_symbols,
            symbols=symbols,
            risk_free_rate=risk_free_rate,
            holdings_df=st.session_state.holdings
        )

    with tabs[5]:
        render_reports_tab(
            metrics=metrics,
            position_metrics=position_metrics,
            exante=exante,
            benchmark=benchmark,
            var_confidence=var_confidence,
            total_value=total_value,
            hist_var=hist_var,
            hist_cvar=hist_cvar,
            param_var=param_var,
            param_cvar=param_cvar,
            portfolio_returns=portfolio_returns,
            benchmark_returns=benchmark_returns,
            risk_free_rate=risk_free_rate,
            holdings_df=st.session_state.holdings,
            transactions_df=st.session_state.transactions,
            stress_results=None
        )

    render_footer()


if __name__ == "__main__":
    main()
