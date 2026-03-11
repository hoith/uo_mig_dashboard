# ui/tabs/overview.py
import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px


def render_overview_tab(metrics, portfolio_df, benchmark_returns, position_metrics,
                        benchmark, adjusted_benchmark, total_value, total_cost,
                        portfolio_returns, twr_total, mwr_total):
    """Render the Overview tab."""
    st.markdown("## Portfolio Overview")

    # -------------------------------------------------------------------------
    # KPI Row 1 — Returns Since Inception
    # -------------------------------------------------------------------------
    st.markdown("##### Returns Since Inception")
    col1, col2, col3, col4 = st.columns(4)

    total_pnl = total_value - total_cost
    adj_bench_total = metrics.get('adjusted_benchmark_total', 0)
    twr_ann = metrics.get('twr_annualized', 0)
    adj_bench_ann = metrics.get('adjusted_benchmark_return', 0)
    beta_ex_cash = metrics.get('beta_ex_cash', 1)

    with col1:
        st.metric(
            "Portfolio Value",
            f"${total_value:,.0f}",
            f"P&L: ${total_pnl:,.0f}" if total_cost > 0 else "N/A"
        )
    with col2:
        st.metric(
            "TWR (Total)",
            f"{twr_total:.1%}",
            f"vs Benchmark: {(twr_total - adj_bench_total):+.1%}"
        )
    with col3:
        st.metric(
            f"{benchmark} Return (Total)",
            f"{adj_bench_total:.1%}",
            "Cash-flow adjusted"
        )
    with col4:
        st.metric(
            "MWR (Total)",
            f"{mwr_total:.1%}",
            "Investor money-weighted return"
        )

    # -------------------------------------------------------------------------
    # KPI Row 2 — Annualised & Risk
    # -------------------------------------------------------------------------
    st.markdown("##### Annualised & Risk Metrics")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "TWR (Annualised)",
            f"{twr_ann:.1%}",
            f"vs Bench: {(twr_ann - adj_bench_ann):+.1%}"
        )
    with col2:
        st.metric(
            "Volatility (Ann.)",
            f"{metrics.get('volatility', 0):.1%}",
            f"Sharpe: {metrics.get('sharpe_ratio', 0):.2f}"
        )
    with col3:
        st.metric(
            "Max Drawdown",
            f"{metrics.get('max_drawdown', 0):.1%}",
            f"Calmar: {metrics.get('calmar_ratio', 0):.2f}"
        )
    with col4:
        st.metric(
            "Sortino Ratio",
            f"{metrics.get('sortino_ratio', 0):.2f}",
            f"Beta (ex-cash): {beta_ex_cash:.2f}"
        )

    # -------------------------------------------------------------------------
    # KPI Row 3 — Relative Performance / Capture Ratios
    # -------------------------------------------------------------------------
    st.markdown("##### Relative Performance")
    col1, col2, col3, col4 = st.columns(4)

    if not portfolio_returns.empty and not benchmark_returns.empty:
        _cap = pd.concat([portfolio_returns, benchmark_returns], axis=1, join='inner')
        _cap.columns = ['p', 'b']
        _up = _cap[_cap['b'] > 0]
        _dn = _cap[_cap['b'] < 0]
        _bu = (1 + _up['b']).prod() - 1 if len(_up) else 0
        _pu = (1 + _up['p']).prod() - 1 if len(_up) else 0
        _bd = (1 + _dn['b']).prod() - 1 if len(_dn) else 0
        _pd = (1 + _dn['p']).prod() - 1 if len(_dn) else 0
        upside_capture   = (_pu / _bu * 100) if _bu != 0 else 100.0
        downside_capture = (_pd / _bd * 100) if _bd != 0 else 100.0
        win_rate_vs_bench = (_cap['p'] > _cap['b']).mean()
        tracking_error   = metrics.get('tracking_error', 0)
        info_ratio       = metrics.get('information_ratio', 0)
    else:
        upside_capture = downside_capture = 100.0
        win_rate_vs_bench = tracking_error = info_ratio = 0.0

    with col1:
        st.metric(
            "Upside Capture",
            f"{upside_capture:.1f}%",
            "↑ Gains in up markets" if upside_capture > 100 else "↓ Misses some upside"
        )
    with col2:
        st.metric(
            "Downside Capture",
            f"{downside_capture:.1f}%",
            "↑ Over-exposed in down markets" if downside_capture > 100 else "↓ Cushioned in down markets"
        )
    with col3:
        st.metric(
            "Win Rate vs Benchmark",
            f"{win_rate_vs_bench:.1%}",
            "Daily outperformance frequency"
        )
    with col4:
        st.metric(
            "Information Ratio",
            f"{info_ratio:.2f}",
            f"Tracking Error: {tracking_error:.1%}"
        )

    with st.expander("Metrics Explained"):
        st.markdown("""
        - **TWR**: Time-Weighted Return — manager skill, eliminates cash flow timing effects
        - **MWR**: Money-Weighted Return (IRR) — investor experience, reflects cash flow timing
        - **Adjusted Benchmark**: Benchmark return replicated with same deposit/withdrawal schedule
        - **Upside / Downside Capture**: How much of the benchmark's up/down moves the portfolio captures
        - **Information Ratio**: Active return per unit of tracking error
        - **Beta (ex-cash)**: Market sensitivity of the securities book only (excludes cash drag)
        """)

    st.markdown("---")

    # -------------------------------------------------------------------------
    # Cumulative Performance + Allocation
    # -------------------------------------------------------------------------
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### Cumulative Performance")

        if not portfolio_returns.empty:
            cum_portfolio = (1 + portfolio_returns).cumprod() - 1
            cum_benchmark = (1 + benchmark_returns).cumprod() - 1

            aligned = pd.concat([cum_portfolio, cum_benchmark], axis=1, join='inner')
            aligned.columns = ['Portfolio', benchmark]

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=aligned.index, y=aligned['Portfolio'],
                mode='lines', name='Portfolio (TWR)',
                line=dict(color='#FEE123', width=2)
            ))
            fig.add_trace(go.Scatter(
                x=aligned.index, y=aligned[benchmark],
                mode='lines', name=benchmark,
                line=dict(color='#00C805', width=2)
            ))
            fig.update_layout(
                template='plotly_dark',
                font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                height=380,
                margin=dict(l=20, r=20, t=30, b=20),
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                xaxis=dict(gridcolor='#1a1a1a'),
                yaxis=dict(gridcolor='#1a1a1a', tickformat='.1%')
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### Allocation")
        if not position_metrics.empty:
            fig = px.pie(
                position_metrics, values='Market Value', names='Symbol', hole=0.4,
                color_discrete_sequence=['#FEE123','#00C805','#FFD700','#FF0000',
                                         '#4488FF','#154733','#00A36C','#FF9900',
                                         '#666666','#AAAAAA']
            )
            fig.update_layout(
                template='plotly_dark',
                font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                height=380,
                margin=dict(l=20, r=20, t=30, b=20),
                showlegend=True,
                legend=dict(orientation='h', yanchor='bottom', y=-0.2)
            )
            st.plotly_chart(fig, use_container_width=True)

    # -------------------------------------------------------------------------
    # Drawdown  |  Cumulative Active Return  (side-by-side)
    # -------------------------------------------------------------------------
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Drawdown")
        if not portfolio_returns.empty:
            _cum = (1 + portfolio_returns).cumprod()
            _roll_max = _cum.expanding().max()
            _dd = (_cum - _roll_max) / _roll_max

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=_dd.index, y=_dd.values,
                fill='tozeroy', mode='lines', name='Drawdown',
                line=dict(color='#FF0000', width=1),
                fillcolor='rgba(255,0,0,0.2)'
            ))
            fig.update_layout(
                template='plotly_dark',
                font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                height=250, margin=dict(l=20, r=20, t=20, b=20),
                xaxis=dict(gridcolor='#1a1a1a'),
                yaxis=dict(gridcolor='#1a1a1a', tickformat='.1%'),
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### Cumulative Active Return")
        if not portfolio_returns.empty and not benchmark_returns.empty:
            _a = pd.concat([portfolio_returns, benchmark_returns], axis=1, join='inner')
            _a.columns = ['p', 'b']
            _cum_p = (1 + _a['p']).cumprod() - 1
            _cum_b = (1 + _a['b']).cumprod() - 1
            _alpha = _cum_p - _cum_b

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=_alpha.index, y=_alpha.values,
                fill='tozeroy', mode='lines', name='Active Return',
                line=dict(color='#FEE123', width=1.5),
                fillcolor='rgba(254,225,35,0.15)'
            ))
            fig.add_hline(y=0, line_color='#444444', line_width=1)
            fig.update_layout(
                template='plotly_dark',
                font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                height=250, margin=dict(l=20, r=20, t=20, b=20),
                xaxis=dict(gridcolor='#1a1a1a'),
                yaxis=dict(gridcolor='#1a1a1a', tickformat='.1%'),
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)

    # -------------------------------------------------------------------------
    # Monthly Returns Heatmap
    # -------------------------------------------------------------------------
    st.markdown("### Monthly Returns")
    if not portfolio_returns.empty:
        try:
            _monthly = portfolio_returns.resample('ME').apply(lambda x: (1 + x).prod() - 1)
        except Exception:
            _monthly = portfolio_returns.resample('M').apply(lambda x: (1 + x).prod() - 1)

        if not _monthly.empty:
            _mdf = _monthly.reset_index()
            _mdf.columns = ['Date', 'Return']
            _mdf['Year']  = _mdf['Date'].dt.year
            _mdf['Month'] = _mdf['Date'].dt.month
            _pivot = _mdf.pivot(index='Year', columns='Month', values='Return')
            _month_labels = ['Jan','Feb','Mar','Apr','May','Jun',
                             'Jul','Aug','Sep','Oct','Nov','Dec']
            _pivot.columns = [_month_labels[m - 1] for m in _pivot.columns]

            fig = px.imshow(
                _pivot,
                text_auto='.1%',
                color_continuous_scale='RdYlGn',
                color_continuous_midpoint=0,
                aspect='auto',
                labels=dict(color='Return')
            )
            fig.update_layout(
                template='plotly_dark',
                font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                height=max(160, len(_pivot) * 48 + 80),
                margin=dict(l=20, r=20, t=40, b=20),
                xaxis=dict(side='top'),
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig, use_container_width=True)
