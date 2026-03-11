# ui/layout.py
import streamlit as st
from datetime import datetime


def render_header():
    """Render Bloomberg-style header."""
    st.markdown("""
    <div style="padding: 4px 0; border-bottom: 1px solid #333333; margin-bottom: 8px;">
        <span style="font-size: 1.3rem; color: #FEE123; text-transform: uppercase;
                     letter-spacing: 0.1em; font-family: 'JetBrains Mono', monospace;
                     font-weight: 700;">
            UO MIG PORTFOLIO RISK DASHBOARD
        </span>
    </div>
    """, unsafe_allow_html=True)


def render_ticker_bar(selected_portfolio, total_value, total_pnl, twr_total,
                      benchmark, adj_bench_total, beta_ex_cash):
    """Render the live data ticker strip."""
    _chg_color = '#00C805' if twr_total >= 0 else '#FF0000'
    st.markdown(f"""
    <div style="background-color: #111111; border: 1px solid #333333; border-radius: 0px;
                padding: 6px 16px; margin-bottom: 8px; display: flex; justify-content: space-between;
                align-items: center; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem;
                overflow-x: auto; white-space: nowrap;">
        <span style="color: #FEE123; font-weight: 700;">{selected_portfolio.upper()}</span>
        <span style="color: #333333;">|</span>
        <span style="color: #999999;">NAV</span>&nbsp;
        <span style="color: #FFFFFF; font-weight: 700;">${total_value:,.0f}</span>
        <span style="color: #333333;">|</span>
        <span style="color: #999999;">P&amp;L</span>&nbsp;
        <span style="color: {_chg_color}; font-weight: 700;">${total_pnl:+,.0f}</span>
        <span style="color: #333333;">|</span>
        <span style="color: #999999;">TWR</span>&nbsp;
        <span style="color: {_chg_color}; font-weight: 700;">{twr_total:+.2%}</span>
        <span style="color: #333333;">|</span>
        <span style="color: #999999;">BENCH</span>&nbsp;
        <span style="color: #FEE123;">{benchmark}</span>
        <span style="color: #333333;">|</span>
        <span style="color: #999999;">AS OF</span>&nbsp;
        <span style="color: #E0E0E0;">{datetime.now().strftime('%Y-%m-%d')}</span>
    </div>
    """, unsafe_allow_html=True)


def render_footer():
    """Render the footer."""
    st.markdown("""
    <div style="text-align: center; color: #666666; padding: 0.5rem 0;
                font-family: 'JetBrains Mono', monospace; font-size: 0.7rem;
                text-transform: uppercase; letter-spacing: 0.05em;
                border-top: 1px solid #333333; margin-top: 1rem;">
        UO MIG PORTFOLIO RISK DASHBOARD V1.0 | DATA: YAHOO FINANCE | EDUCATIONAL USE ONLY
    </div>
    """, unsafe_allow_html=True)
