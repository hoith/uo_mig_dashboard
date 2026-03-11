# ui/sidebar.py
import streamlit as st
from datetime import datetime, date
from config import PORTFOLIO_CONFIG
from data.fetchers import fetch_risk_free_rate
from state import reload_portfolio


def render_sidebar():
    """
    Render the sidebar UI and return all user-selected parameters.

    Returns:
        dict with keys: start_date, end_date, benchmark, var_confidence,
                        enable_crp, position_limit, risk_free_rate
    """
    with st.sidebar:
        st.markdown("### CONFIGURATION")

        # Portfolio Selector
        st.markdown("### PORTFOLIO SELECTION")
        portfolio_options = list(PORTFOLIO_CONFIG.keys())

        # Initialize selected portfolio in session state
        if 'selected_portfolio' not in st.session_state:
            st.session_state.selected_portfolio = portfolio_options[0]

        selected_portfolio = st.selectbox(
            "Select Portfolio",
            options=portfolio_options,
            index=portfolio_options.index(st.session_state.selected_portfolio),
            help="Switch between different portfolios"
        )

        # Reload data when portfolio changes
        if selected_portfolio != st.session_state.selected_portfolio:
            reload_portfolio(selected_portfolio)

        st.markdown("---")

        # Date range - default to cover transaction history
        st.markdown("### DATE RANGE")

        # Fixed start date as per requirement: March 31, 2025
        default_start = datetime(2025, 3, 31)

        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "Start",
                value=default_start,
                max_value=datetime.now()
            )
        with col2:
            end_date = st.date_input(
                "End",
                value=datetime.now(),
                max_value=datetime.now()
            )

        st.markdown("---")

        # Benchmark
        st.markdown("### BENCHMARK")
        benchmark = st.selectbox(
            "Select Benchmark",
            options=['SPY', 'QQQ', 'IWM', 'DIA', 'VTI', 'AGG', 'IEMG'],
            index=0,
            help="Benchmark for relative performance metrics"
        )

        st.markdown("---")

        # Risk parameters
        st.markdown("### RISK PARAMETERS")
        var_confidence = st.slider(
            "VaR Confidence Level",
            min_value=0.90,
            max_value=0.99,
            value=0.95,
            step=0.01,
            format="%.2f"
        )

        enable_crp = st.toggle(
            "Enable Country Risk Premium",
            value=True,
            help="Adjust returns for country-specific risk premiums"
        )

        position_limit = st.slider(
            "Max Position Weight (%)",
            min_value=5,
            max_value=50,
            value=25,
            step=5
        )

        st.markdown("---")

        # Risk-free rate (auto-fetched from 13-week T-bill)
        live_rf_rate = fetch_risk_free_rate()
        risk_free_rate = st.number_input(
            "Risk-Free Rate (%)",
            min_value=0.0,
            max_value=10.0,
            value=live_rf_rate,
            step=0.1,
            help=f"Auto-fetched from 13-week T-bill (^IRX): {live_rf_rate:.2f}%"
        ) / 100

    return {
        'start_date': start_date,
        'end_date': end_date,
        'benchmark': benchmark,
        'var_confidence': var_confidence,
        'enable_crp': enable_crp,
        'position_limit': position_limit,
        'risk_free_rate': risk_free_rate,
    }
