# calculations/portfolio.py
import pandas as pd
import numpy as np
from config import TICKER_COUNTRY_MAP


def calculate_cash_from_transactions(transactions_df, initial_cash=0.0):
    """Calculate cash balance from transaction history.

    Supports transaction types:
        - BUY: Purchase securities (reduces cash)
        - SELL: Sell securities (increases cash)
        - WITHDRAWAL: Cash withdrawn from portfolio (reduces cash)
        - DEPOSIT: Cash added to portfolio (increases cash)
        - REBALANCE: Cash rebalancing/withdrawal (reduces cash, use negative amount for deposit)

    Args:
        transactions_df: DataFrame with columns: date, symbol, side, quantity, price, fees
                        For WITHDRAWAL/DEPOSIT/REBALANCE: use 'quantity' as the cash amount, price=1
        initial_cash: Starting cash balance

    Returns:
        tuple: (current_cash_balance, total_withdrawals, total_deposits)
    """
    if transactions_df is None or transactions_df.empty:
        return initial_cash, 0.0, 0.0

    cash_current = initial_cash
    total_withdrawals = 0.0
    total_deposits = 0.0

    # Sort transactions by date
    txns = transactions_df.sort_values('date').copy()

    for _, txn in txns.iterrows():
        quantity = float(txn.get('quantity', 0) or 0)
        price = float(txn.get('price', 0) or 0)
        fees = float(txn.get('fees', 0) or 0)
        side = str(txn.get('side', '')).upper()

        if side == 'SELL':
            # Selling adds cash (proceeds minus fees)
            cash_current += quantity * price - fees
        elif side == 'BUY':
            # Buying reduces cash (cost plus fees)
            cash_current -= quantity * price + fees
        elif side in ['WITHDRAWAL', 'REBALANCE']:
            # Withdrawal/rebalance removes cash from portfolio
            # quantity represents the cash amount being withdrawn
            withdrawal_amount = quantity * price if price > 0 else quantity
            cash_current -= withdrawal_amount
            total_withdrawals += withdrawal_amount
        elif side == 'DEPOSIT':
            # Deposit adds cash to portfolio
            deposit_amount = quantity * price if price > 0 else quantity
            cash_current += deposit_amount
            total_deposits += deposit_amount

    return round(cash_current, 2), round(total_withdrawals, 2), round(total_deposits, 2)


def reconstruct_portfolio_from_initial(transactions_df, initial_holdings_df, prices_df, initial_cash=0.0):
    """
    Reconstruct portfolio timeline from initial holdings + transactions.

    This properly tracks holdings through time by:
    1. Starting with initial holdings (from holdings.csv)
    2. Applying transactions in chronological order
    3. Tracking cash balance through time

    Args:
        transactions_df: DataFrame with columns: date, symbol, side, quantity, price, fees
        initial_holdings_df: DataFrame with initial holdings (symbol, quantity)
        prices_df: DataFrame with daily prices for each symbol
        initial_cash: Starting cash balance

    Returns:
        tuple: (portfolio_df, weights_df, cash_flows_df, current_holdings_df)
            - portfolio_df: Daily portfolio values with securities_value, cash, total_value
            - weights_df: Daily position weights
            - cash_flows_df: External cash flows (deposits/withdrawals) for TWR calculation
            - current_holdings_df: DataFrame with current holdings after all transactions
    """
    if prices_df is None or prices_df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # Initialize holdings from initial snapshot (excluding CASH row)
    holdings = {}
    for _, row in initial_holdings_df.iterrows():
        symbol = row['symbol']
        if symbol.upper() != 'CASH':
            holdings[symbol] = row['quantity']

    # Prepare transactions sorted by date
    if transactions_df is not None and not transactions_df.empty:
        txns = transactions_df.sort_values('date').copy()
        txns['date'] = pd.to_datetime(txns['date'])
    else:
        txns = pd.DataFrame(columns=['date', 'symbol', 'side', 'quantity', 'price', 'fees'])

    # Infer initial positions for symbols that appear in sell transactions
    # but aren't in initial holdings (to avoid phantom cash from selling non-existent positions)
    if not txns.empty:
        for symbol in txns['symbol'].unique():
            if not symbol or not isinstance(symbol, str) or symbol.upper() == 'CASH':
                continue
            symbol_txns = txns[txns['symbol'] == symbol].sort_values('date')
            running_qty = holdings.get(symbol, 0)
            min_qty = running_qty
            for _, txn in symbol_txns.iterrows():
                side = str(txn.get('side', '')).upper()
                qty = float(txn.get('quantity', 0) or 0)
                if side == 'BUY':
                    running_qty += qty
                elif side == 'SELL':
                    running_qty -= qty
                min_qty = min(min_qty, running_qty)
            if min_qty < 0:
                # Need additional shares in initial holdings to avoid going negative
                holdings[symbol] = holdings.get(symbol, 0) + abs(min_qty)

    # For symbols without price data (e.g. delisted), create synthetic prices
    # using the earliest transaction price so the position is properly valued
    # and sells convert position → cash without creating phantom value
    if not txns.empty:
        for symbol in txns['symbol'].unique():
            if not symbol or not isinstance(symbol, str) or symbol.upper() == 'CASH':
                continue
            if symbol not in prices_df.columns:
                # Use the earliest transaction price as a flat synthetic price
                symbol_txns = txns[txns['symbol'] == symbol].sort_values('date')
                first_price = float(symbol_txns.iloc[0]['price'])
                if first_price > 0:
                    prices_df[symbol] = first_price

    # Track cash flows for TWR calculation (external flows only: deposits/withdrawals)
    cash_flows = []  # List of (date, amount) - positive = inflow, negative = outflow

    # Build daily portfolio values
    portfolio_data = []
    cash_balance = initial_cash

    # Get all trading dates from prices
    dates = prices_df.index.tolist()
    first_price_date = pd.Timestamp(dates[0]).normalize() if dates else None

    # Create a dict to quickly lookup transactions by date
    txn_by_date = {}
    pre_period_txns = []  # Transactions BEFORE first price date

    for _, txn in txns.iterrows():
        txn_date = pd.Timestamp(txn['date']).normalize()
        if first_price_date and txn_date < first_price_date:
            # Transaction happened before our price data starts
            pre_period_txns.append(txn)
        else:
            if txn_date not in txn_by_date:
                txn_by_date[txn_date] = []
            txn_by_date[txn_date].append(txn)

    # Apply all transactions that happened BEFORE the first price date
    # These adjust our starting holdings but don't count as cash flows for TWR
    for txn in sorted(pre_period_txns, key=lambda x: x['date']):
        symbol = txn['symbol']
        side = txn['side'].upper()
        quantity = txn['quantity']
        price = txn['price']
        fees = txn.get('fees', 0) or 0

        if side == 'BUY':
            holdings[symbol] = holdings.get(symbol, 0) + quantity
            cash_balance -= (quantity * price + fees)
        elif side == 'SELL':
            holdings[symbol] = holdings.get(symbol, 0) - quantity
            cash_balance += (quantity * price - fees)
            if holdings.get(symbol, 0) <= 0:
                holdings.pop(symbol, None)
        elif side in ['WITHDRAWAL', 'REBALANCE']:
            amount = quantity * price if price > 0 else quantity
            cash_balance -= amount
            # Note: Pre-period withdrawals don't count as cash flows for TWR
        elif side == 'DEPOSIT':
            amount = quantity * price if price > 0 else quantity
            cash_balance += amount

    for date in dates:
        date_normalized = pd.Timestamp(date).normalize()

        # Apply any transactions on this date BEFORE calculating value
        if date_normalized in txn_by_date:
            for txn in txn_by_date[date_normalized]:
                symbol = txn['symbol']
                side = txn['side'].upper()
                quantity = txn['quantity']
                price = txn['price']
                fees = txn.get('fees', 0) or 0

                if side == 'BUY':
                    # Add to holdings, reduce cash
                    holdings[symbol] = holdings.get(symbol, 0) + quantity
                    cash_balance -= (quantity * price + fees)
                elif side == 'SELL':
                    # Reduce holdings, add to cash
                    holdings[symbol] = holdings.get(symbol, 0) - quantity
                    cash_balance += (quantity * price - fees)
                    # Remove symbol if zero holdings
                    if holdings.get(symbol, 0) <= 0:
                        holdings.pop(symbol, None)
                elif side in ['WITHDRAWAL', 'REBALANCE']:
                    # External cash outflow
                    amount = quantity * price if price > 0 else quantity
                    cash_balance -= amount
                    cash_flows.append({'date': date_normalized, 'amount': -amount})
                elif side == 'DEPOSIT':
                    # External cash inflow
                    amount = quantity * price if price > 0 else quantity
                    cash_balance += amount
                    cash_flows.append({'date': date_normalized, 'amount': amount})

        # Calculate securities value at end of day
        securities_value = 0
        position_values = {}

        for symbol, qty in holdings.items():
            if symbol in prices_df.columns and qty > 0:
                price = prices_df.loc[date, symbol]
                if pd.notna(price):
                    pos_value = qty * price
                    securities_value += pos_value
                    position_values[symbol] = pos_value

        total_value = securities_value + cash_balance  # Include cash (negative = margin/debt)

        portfolio_data.append({
            'date': date,
            'securities_value': securities_value,
            'cash': cash_balance,
            'portfolio_value': total_value,
            **{f'{s}_value': v for s, v in position_values.items()}
        })

    portfolio_df = pd.DataFrame(portfolio_data)
    portfolio_df.set_index('date', inplace=True)

    # Calculate weights
    weights_data = []
    for _, row in portfolio_df.iterrows():
        total = row['portfolio_value']
        if total > 0:
            weights = {}
            for col in portfolio_df.columns:
                if col.endswith('_value') and col != 'securities_value':
                    symbol = col.replace('_value', '')
                    weights[f'{symbol}_weight'] = row[col] / total if col in row else 0
            weights['cash_weight'] = row['cash'] / total if total > 0 else 0
            weights_data.append(weights)

    weights_df = pd.DataFrame(weights_data, index=portfolio_df.index)

    # Create cash flows DataFrame
    cash_flows_df = pd.DataFrame(cash_flows) if cash_flows else pd.DataFrame(columns=['date', 'amount'])

    # Create current holdings DataFrame (final state after all transactions)
    current_holdings_data = []
    for symbol, qty in holdings.items():
        if qty > 0:
            current_holdings_data.append({
                'symbol': symbol,
                'quantity': qty,
                'cost_basis': 0.0,  # Will be calculated separately
                'country': TICKER_COUNTRY_MAP.get(symbol, 'US')
            })
    # Add cash as a position
    if cash_balance > 0:
        current_holdings_data.append({
            'symbol': 'CASH',
            'quantity': cash_balance,
            'cost_basis': 1.0,
            'country': 'US'
        })
    current_holdings_df = pd.DataFrame(current_holdings_data)

    return portfolio_df, weights_df, cash_flows_df, current_holdings_df


def reconstruct_portfolio(transactions_df, holdings_df, prices_df):
    """
    Legacy function: Reconstruct portfolio using current holdings snapshot.

    NOTE: This function uses the FINAL holdings state and applies it across all dates.
    For proper portfolio reconstruction that tracks holdings through time based on
    transactions, use reconstruct_portfolio_from_initial() instead.

    This function is kept for backward compatibility with position metrics calculation.
    """
    if transactions_df is None or transactions_df.empty:
        transactions_df = pd.DataFrame(columns=['date', 'symbol', 'side', 'quantity', 'price', 'fees'])

    symbols = holdings_df['symbol'].unique().tolist()

    # Initialize holdings from current snapshot
    current_holdings = holdings_df.set_index('symbol')['quantity'].to_dict()
    cost_basis = holdings_df.set_index('symbol')['cost_basis'].to_dict()

    # Get price data
    if prices_df is None or prices_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Calculate daily portfolio value
    portfolio_values = []

    for date in prices_df.index:
        daily_value = 0
        for symbol in symbols:
            if symbol in prices_df.columns and symbol in current_holdings:
                price = prices_df.loc[date, symbol]
                if pd.notna(price):
                    daily_value += current_holdings[symbol] * price

        portfolio_values.append({
            'date': date,
            'portfolio_value': daily_value
        })

    portfolio_df = pd.DataFrame(portfolio_values)
    portfolio_df.set_index('date', inplace=True)

    # Calculate weights
    weights_data = []
    for date in prices_df.index:
        total_value = 0
        position_values = {}

        for symbol in symbols:
            if symbol in prices_df.columns and symbol in current_holdings:
                price = prices_df.loc[date, symbol]
                if pd.notna(price):
                    pos_value = current_holdings[symbol] * price
                    position_values[symbol] = pos_value
                    total_value += pos_value

        if total_value > 0:
            weights = {f'{s}_weight': v / total_value for s, v in position_values.items()}
            weights['date'] = date
            weights_data.append(weights)

    weights_df = pd.DataFrame(weights_data)
    if not weights_df.empty:
        weights_df.set_index('date', inplace=True)

    return portfolio_df, weights_df


def calculate_returns(portfolio_df):
    """Calculate portfolio returns time series."""
    if portfolio_df.empty:
        return pd.Series(dtype=float)

    returns = portfolio_df['portfolio_value'].pct_change().dropna()
    return returns
