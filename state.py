# state.py
import streamlit as st
import pandas as pd
from config import PORTFOLIO_CONFIG
from data.loaders import (load_portfolio_transactions, load_portfolio_holdings,
                           load_default_transactions, load_default_holdings)
from calculations.cost_basis import calculate_cost_basis_from_transactions
from calculations.portfolio import calculate_cash_from_transactions


def initialize_session_state():
    """Initialize all session state variables on first load."""
    if 'selected_portfolio' not in st.session_state:
        st.session_state.selected_portfolio = list(PORTFOLIO_CONFIG.keys())[0]

    selected_portfolio = st.session_state.selected_portfolio

    if 'transactions' not in st.session_state:
        st.session_state.transactions = load_portfolio_transactions(selected_portfolio)
    if 'initial_cash' not in st.session_state:
        st.session_state.initial_cash = 0.0
    if 'holdings' not in st.session_state:
        st.session_state.holdings, st.session_state.initial_cash = load_portfolio_holdings(selected_portfolio)
        # Calculate cost basis from transactions if not provided
        if st.session_state.holdings['cost_basis'].sum() == 0:
            st.session_state.holdings = calculate_cost_basis_from_transactions(
                st.session_state.transactions,
                st.session_state.holdings
            )
        # Calculate cash from transactions
        initial_cash = st.session_state.initial_cash
        if initial_cash > 0 or st.session_state.transactions is not None:
            calculated_cash, total_withdrawals, total_deposits = calculate_cash_from_transactions(
                st.session_state.transactions,
                initial_cash
            )
            holdings_df = st.session_state.holdings.copy()
            if 'CASH' in holdings_df['symbol'].values:
                holdings_df.loc[holdings_df['symbol'] == 'CASH', 'quantity'] = calculated_cash
            elif calculated_cash != 0:
                new_cash_row = pd.DataFrame([{
                    'symbol': 'CASH',
                    'quantity': calculated_cash,
                    'cost_basis': 1.0,
                    'country': 'US'
                }])
                holdings_df = pd.concat([holdings_df, new_cash_row], ignore_index=True)
            st.session_state.holdings = holdings_df
    if 'prices_loaded' not in st.session_state:
        st.session_state.prices_loaded = False


def reload_portfolio(portfolio_name):
    """Reload holdings and transactions when portfolio selection changes."""
    st.session_state.selected_portfolio = portfolio_name
    st.session_state.transactions = load_portfolio_transactions(portfolio_name)
    st.session_state.holdings, st.session_state.initial_cash = load_portfolio_holdings(portfolio_name)
    # Calculate cost basis from transactions
    if st.session_state.holdings['cost_basis'].sum() == 0:
        st.session_state.holdings = calculate_cost_basis_from_transactions(
            st.session_state.transactions,
            st.session_state.holdings
        )
    # Calculate cash from transactions (initial_cash now from holdings file)
    initial_cash = st.session_state.initial_cash
    if initial_cash > 0 or st.session_state.transactions is not None:
        calculated_cash, _, _ = calculate_cash_from_transactions(
            st.session_state.transactions,
            initial_cash
        )
        holdings_df = st.session_state.holdings.copy()
        if 'CASH' in holdings_df['symbol'].values:
            holdings_df.loc[holdings_df['symbol'] == 'CASH', 'quantity'] = calculated_cash
        elif calculated_cash != 0:
            new_cash_row = pd.DataFrame([{
                'symbol': 'CASH',
                'quantity': calculated_cash,
                'cost_basis': 1.0,
                'country': 'US'
            }])
            holdings_df = pd.concat([holdings_df, new_cash_row], ignore_index=True)
        st.session_state.holdings = holdings_df
    st.session_state.prices_loaded = False
    st.rerun()
