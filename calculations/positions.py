# calculations/positions.py
import pandas as pd
import numpy as np
from config import TICKER_COUNTRY_MAP, CRP_DATA, IEMG_WEIGHTS


def calculate_exante_metrics(position_metrics, prices_df,
                             index_weights=None, passive_etf='IEMG',
                             benchmark_returns=None):
    """Calculate ex-ante (current-composition) beta and tracking error.

    Ex-ante Beta
    ------------
    Weighted average of individual position betas using current portfolio weights
    and trailing 252-day per-position betas vs the portfolio benchmark.
        β_exante = Σ_i  w_i × β_i

    Individual betas are always computed over the most recent 252 trading days
    (regardless of the user's selected analysis window) so the result reflects
    current market sensitivity rather than a historical average.

    Ex-ante Tracking Error
    ----------------------
    TE = sqrt( w_active' · Σ · w_active )  where Σ is annualised (×252).

    Active weight vector
    --------------------
    For a portfolio that holds the passive ETF alongside individual stocks:
      - passive_etf itself:  w_active = w_portfolio[passive_etf] − 1.0
      - Individual stocks:   w_active = w_portfolio[i] − w_benchmark[i]
      - CASH:                excluded (zero variance, zero index weight)

    Parameters
    ----------
    passive_etf : str
        Ticker of the passive ETF held in the portfolio that represents the
        benchmark (e.g. 'IEMG' for EM benchmark, 'IVV' for S&P 500 benchmark).
    index_weights : dict[str, float]
        Constituent weights (%) for the benchmark index.
    benchmark_returns : pd.Series, optional
        Daily benchmark returns. When provided, individual position betas are
        recalculated over the trailing 252 days using this benchmark, making
        ex-ante beta truly independent of the selected analysis window.
    """
    if position_metrics.empty or prices_df.empty:
        return {}

    if index_weights is None:
        index_weights = IEMG_WEIGHTS

    non_cash = position_metrics[position_metrics['Symbol'] != 'CASH'].copy()
    total_w = non_cash['Weight'].sum()

    # ── Ex-ante Beta ──────────────────────────────────────────────────────────
    # Compute trailing 252-day per-position betas vs the actual benchmark.
    # Falls back to position_metrics['Beta'] (full-window) if data is insufficient.
    _TRAILING = 252
    if benchmark_returns is not None and not benchmark_returns.empty:
        bench_tail = benchmark_returns.iloc[-_TRAILING:]
        fresh_betas = {}
        for _, row in non_cash.iterrows():
            sym = row['Symbol']
            if sym in prices_df.columns:
                pos_ret = prices_df[sym].dropna().pct_change().dropna().iloc[-_TRAILING:]
                aligned = pd.concat([pos_ret, bench_tail], axis=1, join='inner')
                if len(aligned) >= 20:
                    aligned.columns = ['pos', 'bench']
                    cov = np.cov(aligned['pos'].values, aligned['bench'].values)[0, 1]
                    var = aligned['bench'].var()
                    fresh_betas[sym] = cov / var if var > 0 else float(row['Beta'])
                else:
                    fresh_betas[sym] = float(row['Beta'])
            else:
                fresh_betas[sym] = float(row['Beta'])

        beta_w_sum = sum(
            row['Weight'] * fresh_betas.get(row['Symbol'], row['Beta'])
            for _, row in non_cash.iterrows()
        )
        exante_beta = beta_w_sum / total_w if total_w > 0 else 1.0
    else:
        # Fallback: weighted average of full-window betas from position_metrics
        exante_beta = (
            (non_cash['Weight'] * non_cash['Beta']).sum() / total_w
            if total_w > 0 else 1.0
        )

    # ── Ex-ante Tracking Error ────────────────────────────────────────────────
    # TE requires a known passive_etf to define the benchmark weight vector.
    if passive_etf is None:
        return {'exante_beta': exante_beta}

    symbols = [s for s in non_cash['Symbol'].tolist() if s in prices_df.columns]
    if len(symbols) < 2:
        return {'exante_beta': exante_beta}

    returns_df = prices_df[symbols].pct_change().dropna()
    if returns_df.empty or len(returns_df) < 20:
        return {'exante_beta': exante_beta}

    cov_matrix = returns_df.cov() * 252   # annualised covariance matrix

    # Build portfolio weight vector (decimal fractions)
    w_port = {row['Symbol']: row['Weight'] / 100.0
              for _, row in non_cash.iterrows()}

    # Build benchmark weight vector (decimal fractions)
    #   The passive ETF represents 100% of the benchmark allocation
    #   Individual constituents use their index weight
    w_bench = {}
    for sym in symbols:
        if sym == passive_etf:
            w_bench[sym] = 1.0
        else:
            w_bench[sym] = index_weights.get(sym, 0.0) / 100.0

    # Filter to symbols present in covariance matrix
    valid = [s for s in symbols if s in cov_matrix.index]
    if not valid:
        return {'exante_beta': exante_beta}

    w_active_v = np.array([w_port.get(s, 0.0) - w_bench.get(s, 0.0) for s in valid])
    cov_arr = cov_matrix.loc[valid, valid].values

    te_variance = float(w_active_v @ cov_arr @ w_active_v)
    exante_te = np.sqrt(max(te_variance, 0.0))

    return {'exante_beta': exante_beta, 'exante_te': exante_te}


def calculate_position_metrics(holdings_df, prices_df, benchmark_returns=None):
    """Calculate metrics for each position."""
    if holdings_df.empty or prices_df.empty:
        return pd.DataFrame()

    position_data = []

    for _, row in holdings_df.iterrows():
        symbol = row['symbol']
        quantity = row['quantity']
        cost_basis = row.get('cost_basis', 0)

        # Special handling for CASH
        if symbol.upper() == 'CASH':
            market_value = quantity  # Cash quantity IS the value
            position_data.append({
                'Symbol': 'CASH',
                'Quantity': quantity,
                'Cost Basis': 1.0,
                'Current Price': 1.0,
                'Market Value': market_value,
                'Unrealized P&L': 0,
                'P&L %': 0,
                'Weight': 0,
                'Volatility': 0,
                'Beta': 0,
                'Country': 'US',
                'CRP (%)': 0,
            })
            continue

        if symbol in prices_df.columns:
            price_series = prices_df[symbol].dropna()
            if price_series.empty:
                continue

            current_price = price_series.iloc[-1]

            # Handle NaN or zero current price
            if pd.isna(current_price) or current_price == 0:
                continue

            returns = price_series.pct_change().dropna()

            # Calculate position metrics
            market_value = quantity * current_price

            # Handle zero or missing cost basis
            if cost_basis is None or cost_basis == 0 or pd.isna(cost_basis):
                # Use current price as cost basis estimate
                cost_basis = current_price
                total_cost = market_value
                unrealized_pnl = 0
                pnl_pct = 0
            else:
                total_cost = quantity * cost_basis
                unrealized_pnl = market_value - total_cost
                pnl_pct = (current_price / cost_basis - 1) * 100 if cost_basis > 0 else 0

            # Volatility
            vol = returns.std() * np.sqrt(252) if len(returns) > 0 else 0

            # Beta vs benchmark
            beta = 1.0
            if benchmark_returns is not None and not benchmark_returns.empty and len(returns) > 0:
                aligned = pd.concat([returns, benchmark_returns], axis=1, join='inner')
                if len(aligned) > 10:
                    try:
                        cov = np.cov(aligned.iloc[:, 0], aligned.iloc[:, 1])[0, 1]
                        var = aligned.iloc[:, 1].var()
                        beta = cov / var if var > 0 else 1.0
                    except:
                        beta = 1.0

            # Country and CRP
            country = row.get('country', TICKER_COUNTRY_MAP.get(symbol, 'US'))
            if pd.isna(country):
                country = 'US'
            crp = CRP_DATA.get(str(country).upper(), 0)

            position_data.append({
                'Symbol': symbol,
                'Quantity': quantity,
                'Cost Basis': cost_basis,
                'Current Price': current_price,
                'Market Value': market_value,
                'Unrealized P&L': unrealized_pnl,
                'P&L %': pnl_pct,
                'Weight': 0,  # Will be calculated after
                'Volatility': vol,
                'Beta': beta,
                'Country': country,
                'CRP (%)': crp,
            })

    df = pd.DataFrame(position_data)

    # Calculate weights
    if not df.empty:
        total_value = df['Market Value'].sum()
        if total_value > 0:
            df['Weight'] = df['Market Value'] / total_value * 100
        else:
            df['Weight'] = 0

    return df


def calculate_correlation_matrix(prices_df):
    """Calculate correlation matrix from price data."""
    if prices_df.empty:
        return pd.DataFrame()

    returns = prices_df.pct_change().dropna()
    return returns.corr()
