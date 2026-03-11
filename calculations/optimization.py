# calculations/optimization.py
import numpy as np
import pandas as pd
from scipy.optimize import minimize


def optimize_portfolio(returns_df, method='max_sharpe', risk_free_rate=0.05,
                       target_return=None, max_weight=0.25, min_weight=0.02):
    """Optimize portfolio weights using mean-variance optimization."""
    if returns_df.empty:
        return {}

    # Calculate expected returns and covariance
    mean_returns = returns_df.mean() * 252
    cov_matrix = returns_df.cov() * 252
    n_assets = len(mean_returns)

    # Objective functions
    def portfolio_variance(weights):
        return weights.T @ cov_matrix @ weights

    def portfolio_return(weights):
        return weights.T @ mean_returns

    def neg_sharpe_ratio(weights):
        ret = portfolio_return(weights)
        vol = np.sqrt(portfolio_variance(weights))
        return -(ret - risk_free_rate) / vol if vol > 0 else 0

    def min_variance(weights):
        return portfolio_variance(weights)

    # Constraints
    constraints = [
        {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}  # Weights sum to 1
    ]

    if target_return is not None:
        constraints.append({
            'type': 'eq',
            'fun': lambda w: portfolio_return(w) - target_return
        })

    # Bounds
    bounds = tuple((min_weight, max_weight) for _ in range(n_assets))

    # Initial guess (equal weight)
    init_weights = np.array([1/n_assets] * n_assets)

    # Select objective
    if method == 'max_sharpe':
        objective = neg_sharpe_ratio
    elif method == 'min_variance':
        objective = min_variance
    elif method == 'risk_parity':
        def risk_parity_obj(weights):
            port_vol = np.sqrt(portfolio_variance(weights))
            marginal_contrib = cov_matrix @ weights
            risk_contrib = weights * marginal_contrib / port_vol
            target_risk = port_vol / n_assets
            return np.sum((risk_contrib - target_risk) ** 2)
        objective = risk_parity_obj
    else:
        objective = neg_sharpe_ratio

    # Optimize
    try:
        result = minimize(
            objective,
            init_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 1000}
        )

        if result.success:
            optimal_weights = dict(zip(returns_df.columns, result.x))
            opt_return = portfolio_return(result.x)
            opt_vol = np.sqrt(portfolio_variance(result.x))
            opt_sharpe = (opt_return - risk_free_rate) / opt_vol if opt_vol > 0 else 0

            return {
                'weights': optimal_weights,
                'expected_return': opt_return,
                'expected_volatility': opt_vol,
                'sharpe_ratio': opt_sharpe,
                'success': True
            }
    except Exception as e:
        return {'success': False, 'error': str(e)}

    return {'success': False}


def generate_rebalance_transactions(current_holdings, optimal_weights, prices_df, total_value):
    """Generate transactions needed to rebalance to optimal weights."""
    transactions = []

    for symbol, target_weight in optimal_weights.items():
        target_value = total_value * target_weight
        current_qty = current_holdings.get(symbol, 0)

        if symbol in prices_df.columns:
            current_price = prices_df[symbol].iloc[-1]
            current_value = current_qty * current_price
            value_diff = target_value - current_value
            qty_diff = int(value_diff / current_price)

            if abs(qty_diff) > 0:
                transactions.append({
                    'Symbol': symbol,
                    'Side': 'BUY' if qty_diff > 0 else 'SELL',
                    'Quantity': abs(qty_diff),
                    'Est. Price': current_price,
                    'Est. Value': abs(qty_diff) * current_price,
                    'Current Weight': (current_value / total_value * 100) if total_value > 0 else 0,
                    'Target Weight': target_weight * 100,
                })

    return pd.DataFrame(transactions)
