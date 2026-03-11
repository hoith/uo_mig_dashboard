# calculations/performance.py
import pandas as pd
import numpy as np
from config import TRADING_DAYS


def calculate_time_weighted_return(portfolio_df, cash_flows_df):
    """
    Calculate Time-Weighted Return (TWR).

    TWR eliminates the impact of cash flows on performance measurement by:
    1. Splitting the period into sub-periods at each cash flow
    2. Calculating the return for each sub-period
    3. Geometrically linking all sub-period returns

    Formula: TWR = [(1 + R1) × (1 + R2) × ... × (1 + Rn)] - 1

    Args:
        portfolio_df: DataFrame with 'portfolio_value' column and date index
        cash_flows_df: DataFrame with 'date' and 'amount' columns for external flows

    Returns:
        dict: {
            'twr_total': Total time-weighted return,
            'twr_annualized': Annualized TWR,
            'sub_period_returns': List of sub-period returns,
            'daily_twr': Series of daily TWR values for charting
        }
    """
    if portfolio_df.empty or 'portfolio_value' not in portfolio_df.columns:
        return {'twr_total': 0, 'twr_annualized': 0, 'sub_period_returns': [], 'daily_twr': pd.Series()}

    values = portfolio_df['portfolio_value'].dropna()
    if len(values) < 2:
        return {'twr_total': 0, 'twr_annualized': 0, 'sub_period_returns': [], 'daily_twr': pd.Series()}

    # Get cash flow dates
    if cash_flows_df is not None and not cash_flows_df.empty:
        flow_dates = set(pd.to_datetime(cash_flows_df['date']).dt.normalize())
        flow_amounts = cash_flows_df.set_index(pd.to_datetime(cash_flows_df['date']).dt.normalize())['amount'].to_dict()
    else:
        flow_dates = set()
        flow_amounts = {}

    # Calculate daily returns, adjusting for cash flows
    daily_returns = []
    dates = values.index.tolist()

    for i in range(1, len(dates)):
        prev_date = dates[i-1]
        curr_date = dates[i]

        prev_value = values.iloc[i-1]
        curr_value = values.iloc[i]

        # Check if there was a cash flow on the current date
        curr_date_normalized = pd.Timestamp(curr_date).normalize()

        if curr_date_normalized in flow_dates:
            # Cash flow happened at START of this day (before market movement)
            #
            # In reconstruct_portfolio_from_initial, transactions are processed BEFORE
            # calculating the day's ending value.
            #
            # Correct TWR formula for start-of-day cash flow:
            # R = V_end / (V_start + CF) - 1
            #
            # Where:
            # - V_start = previous day's ending value
            # - CF = cash flow (positive for deposit, negative for withdrawal)
            # - V_end = current day's ending value (already reflects the CF in cash balance)
            #
            # This measures return on the capital that was actually invested during the day
            cf = flow_amounts.get(curr_date_normalized, 0)
            adjusted_start_value = prev_value + cf  # Capital at start of day after CF
            if adjusted_start_value > 0:
                ret = (curr_value / adjusted_start_value) - 1
            else:
                ret = 0
        else:
            # No cash flow - simple return
            if prev_value > 0:
                ret = (curr_value / prev_value) - 1
            else:
                ret = 0

        daily_returns.append({'date': curr_date, 'return': ret})

    returns_df = pd.DataFrame(daily_returns).set_index('date')

    # Calculate cumulative TWR (geometric linking)
    cumulative_twr = (1 + returns_df['return']).cumprod()

    # Total TWR
    twr_total = cumulative_twr.iloc[-1] - 1 if len(cumulative_twr) > 0 else 0

    # Annualized TWR
    n_days = (dates[-1] - dates[0]).days
    n_years = n_days / 365.25 if n_days > 0 else 1
    twr_annualized = (1 + twr_total) ** (1 / n_years) - 1 if n_years > 0 else twr_total

    return {
        'twr_total': twr_total,
        'twr_annualized': twr_annualized,
        'sub_period_returns': returns_df['return'].tolist(),
        'daily_twr': cumulative_twr - 1  # Convert to return series
    }


def calculate_money_weighted_return(portfolio_df, cash_flows_df, initial_cash=0.0):
    """
    Calculate Money-Weighted Return (MWR) using Internal Rate of Return (IRR).

    MWR accounts for the timing and size of cash flows, reflecting the
    investor's actual experience. It solves for the discount rate r where:

    NPV = CF_0 + CF_1/(1+r)^t1 + CF_2/(1+r)^t2 + ... + V_final/(1+r)^T = 0

    Args:
        portfolio_df: DataFrame with 'portfolio_value' column and date index
        cash_flows_df: DataFrame with 'date' and 'amount' columns
        initial_cash: Initial investment amount

    Returns:
        dict: {
            'mwr_total': Total money-weighted return,
            'mwr_annualized': Annualized MWR (IRR),
            'xirr': Same as mwr_annualized (industry term)
        }
    """
    if portfolio_df.empty or 'portfolio_value' not in portfolio_df.columns:
        return {'mwr_total': 0, 'mwr_annualized': 0, 'xirr': 0}

    values = portfolio_df['portfolio_value'].dropna()
    if len(values) < 2:
        return {'mwr_total': 0, 'mwr_annualized': 0, 'xirr': 0}

    # Build cash flow series for XIRR calculation
    # Convention: negative = outflow (investment), positive = inflow (withdrawal/final value)
    cash_flow_list = []

    # Initial investment (outflow - negative)
    start_date = values.index[0]
    initial_value = values.iloc[0]
    # The initial investment is the starting portfolio value
    cash_flow_list.append({'date': start_date, 'amount': -initial_value})

    # Intermediate cash flows (deposits are outflows/negative, withdrawals are inflows/positive)
    if cash_flows_df is not None and not cash_flows_df.empty:
        for _, row in cash_flows_df.iterrows():
            # In cash_flows_df: positive = deposit (into portfolio), negative = withdrawal
            # For IRR: we flip the sign (deposit = investor outflow = negative)
            cash_flow_list.append({
                'date': pd.Timestamp(row['date']),
                'amount': -row['amount']  # Flip sign for IRR convention
            })

    # Final value (inflow - positive)
    end_date = values.index[-1]
    final_value = values.iloc[-1]
    cash_flow_list.append({'date': end_date, 'amount': final_value})

    # Sort by date
    cash_flow_list.sort(key=lambda x: x['date'])

    # Calculate XIRR using Newton-Raphson method
    def xnpv(rate, cash_flows):
        """Calculate NPV with exact dates."""
        if rate <= -1:
            return float('inf')
        t0 = cash_flows[0]['date']
        total = 0
        for cf in cash_flows:
            days = (cf['date'] - t0).days
            years = days / 365.25
            total += cf['amount'] / ((1 + rate) ** years)
        return total

    def xirr(cash_flows, guess=0.1):
        """Calculate IRR using Newton-Raphson."""
        rate = guess
        for _ in range(100):  # Max iterations
            npv = xnpv(rate, cash_flows)

            # Numerical derivative
            delta = 0.0001
            npv_delta = xnpv(rate + delta, cash_flows)
            derivative = (npv_delta - npv) / delta

            if abs(derivative) < 1e-10:
                break

            new_rate = rate - npv / derivative

            # Bound the rate to reasonable values
            new_rate = max(-0.99, min(10, new_rate))

            if abs(new_rate - rate) < 1e-7:
                return new_rate
            rate = new_rate

        return rate

    try:
        mwr_annualized = xirr(cash_flow_list)
    except:
        mwr_annualized = 0

    # Calculate total MWR over the period
    n_days = (values.index[-1] - values.index[0]).days
    n_years = n_days / 365.25 if n_days > 0 else 1
    mwr_total = (1 + mwr_annualized) ** n_years - 1

    return {
        'mwr_total': mwr_total,
        'mwr_annualized': mwr_annualized,
        'xirr': mwr_annualized
    }


def calculate_adjusted_benchmark(benchmark_prices, portfolio_df, cash_flows_df):
    """
    Calculate benchmark returns adjusted for the same cash flows as the portfolio.

    When the portfolio has withdrawals/deposits, we adjust the benchmark by
    simulating the same cash flows to enable fair comparison.

    Args:
        benchmark_prices: Series of benchmark prices
        portfolio_df: Portfolio DataFrame with 'portfolio_value'
        cash_flows_df: DataFrame with 'date' and 'amount' columns

    Returns:
        dict: {
            'adjusted_benchmark_values': Series of adjusted benchmark values,
            'adjusted_benchmark_returns': Series of returns,
            'twr': Time-weighted return of adjusted benchmark,
            'raw_benchmark_return': Unadjusted benchmark return for comparison
        }
    """
    if benchmark_prices.empty or portfolio_df.empty:
        return {
            'adjusted_benchmark_values': pd.Series(),
            'adjusted_benchmark_returns': pd.Series(),
            'twr': 0,
            'raw_benchmark_return': 0
        }

    # Align dates
    common_dates = portfolio_df.index.intersection(benchmark_prices.index)
    if len(common_dates) == 0:
        return {
            'adjusted_benchmark_values': pd.Series(),
            'adjusted_benchmark_returns': pd.Series(),
            'twr': 0,
            'raw_benchmark_return': 0
        }

    benchmark_aligned = benchmark_prices.loc[common_dates]
    portfolio_aligned = portfolio_df.loc[common_dates]

    # Get initial portfolio value to set benchmark starting value
    initial_portfolio_value = portfolio_aligned['portfolio_value'].iloc[0]

    # Calculate benchmark "units" (like shares of benchmark ETF)
    initial_benchmark_price = benchmark_aligned.iloc[0]
    benchmark_units = initial_portfolio_value / initial_benchmark_price

    # Build cash flow lookup
    if cash_flows_df is not None and not cash_flows_df.empty:
        flow_lookup = {}
        for _, row in cash_flows_df.iterrows():
            date = pd.Timestamp(row['date']).normalize()
            flow_lookup[date] = flow_lookup.get(date, 0) + row['amount']
    else:
        flow_lookup = {}

    # Calculate adjusted benchmark values
    adjusted_values = []

    for date in common_dates:
        date_normalized = pd.Timestamp(date).normalize()
        benchmark_price = benchmark_aligned.loc[date]

        # Check for cash flow on this date
        if date_normalized in flow_lookup:
            cf = flow_lookup[date_normalized]
            # Positive cf = deposit (add units), negative = withdrawal (remove units)
            units_change = cf / benchmark_price
            benchmark_units += units_change

        adjusted_value = benchmark_units * benchmark_price
        adjusted_values.append({'date': date, 'value': adjusted_value})

    adjusted_df = pd.DataFrame(adjusted_values).set_index('date')
    adjusted_benchmark_values = adjusted_df['value']

    # Calculate returns
    adjusted_benchmark_returns = adjusted_benchmark_values.pct_change().dropna()

    # Calculate raw benchmark return (price return only, no cash flows)
    raw_return = (benchmark_aligned.iloc[-1] / benchmark_aligned.iloc[0]) - 1

    # Calculate time period
    n_days = (common_dates[-1] - common_dates[0]).days
    n_years = n_days / 365.25 if n_days > 0 else 1

    # Raw annualized return (benchmark with no cash flows)
    raw_annualized = (1 + raw_return) ** (1 / n_years) - 1 if n_years > 0 else raw_return

    # Calculate cash-flow adjusted benchmark TWR
    # This is what return you'd get if you invested in benchmark with same cash flows
    # We need to calculate TWR for the adjusted benchmark values
    if len(adjusted_benchmark_values) > 1:
        # Calculate daily returns for adjusted benchmark
        adj_daily_returns = adjusted_benchmark_values.pct_change().dropna()

        # Adjust returns on cash flow days (same logic as portfolio TWR)
        for date_norm, cf in flow_lookup.items():
            if date_norm in adj_daily_returns.index:
                # On cash flow days, the return should exclude the cash flow effect
                # This is already handled since we track units, not just values
                pass

        # Calculate TWR from adjusted returns
        adj_total_return = (1 + adj_daily_returns).prod() - 1
        adj_annualized = (1 + adj_total_return) ** (1 / n_years) - 1 if n_years > 0 else adj_total_return
    else:
        adj_total_return = raw_return
        adj_annualized = raw_annualized

    return {
        'adjusted_benchmark_values': adjusted_benchmark_values,
        'adjusted_benchmark_returns': adjusted_benchmark_returns,
        'adjusted_total': adj_total_return,  # Total cash-flow adjusted benchmark return
        'adjusted_annualized': adj_annualized,  # Annualized cash-flow adjusted benchmark return
        'twr': raw_annualized,  # Raw benchmark TWR (for reference)
        'raw_total': raw_return,  # Total raw benchmark return
        'raw_benchmark_return': raw_return,
        'raw_annualized': raw_annualized
    }


def calculate_performance_metrics(returns, benchmark_returns=None, risk_free_rate=0.05):
    """Calculate comprehensive performance metrics."""
    if returns.empty:
        return {}

    # Align returns
    if benchmark_returns is not None and not benchmark_returns.empty:
        aligned = pd.concat([returns, benchmark_returns], axis=1, join='inner')
        aligned.columns = ['portfolio', 'benchmark']
        returns = aligned['portfolio']
        benchmark_returns = aligned['benchmark']

    # Basic metrics
    total_return = (1 + returns).prod() - 1
    trading_days = TRADING_DAYS
    n_years = len(returns) / trading_days
    annualized_return = (1 + total_return) ** (1 / max(n_years, 0.01)) - 1

    # Risk metrics
    volatility = returns.std() * np.sqrt(trading_days)

    # Sharpe Ratio
    excess_return = annualized_return - risk_free_rate
    sharpe_ratio = excess_return / volatility if volatility > 0 else 0

    # Sortino Ratio (downside deviation)
    downside_returns = returns[returns < 0]
    downside_std = downside_returns.std() * np.sqrt(trading_days) if len(downside_returns) > 0 else volatility
    sortino_ratio = excess_return / downside_std if downside_std > 0 else 0

    # Maximum Drawdown
    cumulative = (1 + returns).cumprod()
    rolling_max = cumulative.expanding().max()
    drawdowns = (cumulative - rolling_max) / rolling_max
    max_drawdown = drawdowns.min()

    # Calmar Ratio
    calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0

    metrics = {
        'total_return': total_return,
        'annualized_return': annualized_return,
        'volatility': volatility,
        'sharpe_ratio': sharpe_ratio,
        'sortino_ratio': sortino_ratio,
        'max_drawdown': max_drawdown,
        'calmar_ratio': calmar_ratio,
        'positive_days': (returns > 0).mean(),
        'best_day': returns.max(),
        'worst_day': returns.min(),
        'avg_daily_return': returns.mean(),
        'skewness': returns.skew(),
        'kurtosis': returns.kurtosis(),
    }

    # Benchmark-relative metrics
    if benchmark_returns is not None and not benchmark_returns.empty:
        # Beta
        covariance = np.cov(returns.values, benchmark_returns.values)[0, 1]
        benchmark_variance = benchmark_returns.var()
        beta = covariance / benchmark_variance if benchmark_variance > 0 else 1

        # Alpha (Jensen's)
        benchmark_ann_return = (1 + benchmark_returns).prod() ** (trading_days / len(benchmark_returns)) - 1
        alpha = annualized_return - (risk_free_rate + beta * (benchmark_ann_return - risk_free_rate))

        # R-squared
        correlation = returns.corr(benchmark_returns)
        r_squared = correlation ** 2

        # Tracking Error
        tracking_diff = returns - benchmark_returns
        tracking_error = tracking_diff.std() * np.sqrt(trading_days)

        # Information Ratio
        information_ratio = (annualized_return - benchmark_ann_return) / tracking_error if tracking_error > 0 else 0

        metrics.update({
            'beta': beta,
            'alpha': alpha,
            'r_squared': r_squared,
            'tracking_error': tracking_error,
            'information_ratio': information_ratio,
            'benchmark_return': benchmark_ann_return,
        })

    return metrics
