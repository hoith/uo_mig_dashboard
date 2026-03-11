# calculations/risk.py
import pandas as pd
import numpy as np
from scipy import stats


def calculate_var_cvar(returns, confidence=0.95, method='historical'):
    """Calculate Value at Risk and Conditional VaR."""
    if returns.empty:
        return 0, 0

    if method == 'historical':
        var = np.percentile(returns, (1 - confidence) * 100)
        cvar = returns[returns <= var].mean()
    elif method == 'parametric':
        mean = returns.mean()
        std = returns.std()
        z_score = stats.norm.ppf(1 - confidence)
        var = mean + z_score * std
        cvar = mean - std * stats.norm.pdf(z_score) / (1 - confidence)

    return var, cvar


def monte_carlo_simulation(returns, n_simulations=10000, n_days=252, initial_value=100000):
    """Run Monte Carlo simulation for portfolio."""
    if returns.empty:
        return np.array([]), np.array([])

    mean_return = returns.mean()
    std_return = returns.std()

    simulations = np.zeros((n_simulations, n_days))
    simulations[:, 0] = initial_value

    for t in range(1, n_days):
        random_returns = np.random.normal(mean_return, std_return, n_simulations)
        simulations[:, t] = simulations[:, t-1] * (1 + random_returns)

    final_values = simulations[:, -1]

    return simulations, final_values


def run_stress_tests(holdings_df, prices_df, scenarios=None):
    """Run stress test scenarios on portfolio."""
    if scenarios is None:
        scenarios = {
            'Market Crash (-30%)': {'market': -0.30},
            'Tech Selloff (-25% tech, -10% others)': {'tech': -0.25, 'other': -0.10},
            'Interest Rate Shock': {'rate_sensitive': -0.15, 'growth': -0.20},
            'Currency Crisis (EM -40%)': {'em': -0.40, 'dm': -0.05},
            'Inflation Surge': {'growth': -0.15, 'value': 0.05},
            'Black Swan (-50%)': {'market': -0.50},
        }

    tech_symbols = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'META', 'AMZN', 'ADBE']
    em_symbols = ['BABA', 'FXI', 'EEM']
    cash_symbols = ['CASH']  # Cash is not affected by market shocks

    results = []

    for scenario_name, shocks in scenarios.items():
        total_loss = 0

        for _, row in holdings_df.iterrows():
            symbol = row['symbol']
            quantity = row['quantity']

            # CASH is not affected by market shocks
            if symbol.upper() == 'CASH':
                continue

            if symbol in prices_df.columns:
                current_price = prices_df[symbol].iloc[-1]
                position_value = quantity * current_price

                # Apply appropriate shock
                shock = shocks.get('market', 0)
                if symbol in tech_symbols and 'tech' in shocks:
                    shock = shocks['tech']
                elif symbol in em_symbols and 'em' in shocks:
                    shock = shocks['em']
                elif 'other' in shocks and symbol not in tech_symbols:
                    shock = shocks['other']
                elif 'dm' in shocks and symbol not in em_symbols:
                    shock = shocks['dm']

                total_loss += position_value * shock

        # Calculate total portfolio including cash
        total_portfolio = 0
        for _, row in holdings_df.iterrows():
            symbol = row['symbol']
            if symbol.upper() == 'CASH':
                total_portfolio += row['quantity']
            elif symbol in prices_df.columns:
                total_portfolio += row['quantity'] * prices_df[symbol].iloc[-1]

        results.append({
            'Scenario': scenario_name,
            'Portfolio Loss ($)': total_loss,
            'Portfolio Loss (%)': (total_loss / total_portfolio * 100) if total_portfolio > 0 else 0,
        })

    return pd.DataFrame(results)
