# ui/tabs/overview.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px


def render_overview_tab(metrics, portfolio_df, benchmark_returns, position_metrics,
                        benchmark, adjusted_benchmark, total_value, total_cost,
                        portfolio_returns, twr_total, mwr_total):
    """Render the Overview tab."""
    st.markdown("## Portfolio Overview")

    # KPI Cards Row 1 - Returns (Total, Since Inception)
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
            "Portfolio Return (Total)",
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
            "Beta (Ex-Cash)",
            f"{beta_ex_cash:.2f}",
            f"vs {benchmark}"
        )

    # KPI Cards Row 2 - Annualized & Risk Metrics
    st.markdown("##### Annualized & Risk Metrics")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "TWR (Annualized)",
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
            "Downside risk"
        )

    # Compact explanation
    with st.expander("Metrics Explained"):
        st.markdown("""
        - **Total Return**: Cumulative return since inception (not annualized)
        - **TWR (Annualized)**: Time-Weighted Return - manager performance excluding cash flow timing
        - **Adjusted Benchmark**: Benchmark return with same cash flows as your portfolio
        - **Beta (Ex-Cash)**: Market sensitivity of securities only (excludes cash drag)
        """)

    st.markdown("---")

    # Performance Chart
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### Cumulative Performance (Cash-Flow Adjusted)")

        if not portfolio_returns.empty:
            # Calculate cumulative returns
            cum_portfolio = (1 + portfolio_returns).cumprod()

            # Use adjusted benchmark values (already accounts for same cash flows)
            adj_bench_values = adjusted_benchmark.get('adjusted_benchmark_values', pd.Series())
            if not adj_bench_values.empty:
                # Normalize to start at 1
                cum_adj_benchmark = adj_bench_values / adj_bench_values.iloc[0]
            else:
                cum_adj_benchmark = (1 + benchmark_returns).cumprod()

            # Also show raw benchmark for comparison
            cum_raw_benchmark = (1 + benchmark_returns).cumprod()

            # Align indices
            aligned = pd.concat([cum_portfolio, cum_adj_benchmark, cum_raw_benchmark], axis=1, join='inner')
            aligned.columns = ['Portfolio', f'{benchmark} (Adj.)', f'{benchmark} (Raw)']

            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=aligned.index,
                y=aligned['Portfolio'],
                mode='lines',
                name='Portfolio',
                line=dict(color='#FEE123', width=2)
            ))

            fig.add_trace(go.Scatter(
                x=aligned.index,
                y=aligned[f'{benchmark} (Adj.)'],
                mode='lines',
                name=f'{benchmark} (Cash-Flow Adjusted)',
                line=dict(color='#00C805', width=2)
            ))

            fig.add_trace(go.Scatter(
                x=aligned.index,
                y=aligned[f'{benchmark} (Raw)'],
                mode='lines',
                name=f'{benchmark} (Raw)',
                line=dict(color='#666666', width=2, dash='dash')
            ))

            fig.update_layout(
                template='plotly_dark',
                font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=400,
                margin=dict(l=20, r=20, t=30, b=20),
                legend=dict(
                    orientation='h',
                    yanchor='bottom',
                    y=1.02,
                    xanchor='right',
                    x=1
                ),
                xaxis=dict(gridcolor='#1a1a1a'),
                yaxis=dict(gridcolor='#1a1a1a', tickformat='.1%')
            )

            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### Allocation")

        if not position_metrics.empty:
            fig = px.pie(
                position_metrics,
                values='Market Value',
                names='Symbol',
                hole=0.4,
                color_discrete_sequence=['#FEE123', '#00C805', '#FFD700', '#FF0000', '#4488FF', '#154733', '#00A36C', '#FF9900', '#666666', '#AAAAAA']
            )

            fig.update_layout(
                template='plotly_dark',
                font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=400,
                margin=dict(l=20, r=20, t=30, b=20),
                showlegend=True,
                legend=dict(
                    orientation='h',
                    yanchor='bottom',
                    y=-0.2
                )
            )

            st.plotly_chart(fig, use_container_width=True)

    # Drawdown chart
    st.markdown("### Drawdown Analysis")

    if not portfolio_returns.empty:
        cumulative = (1 + portfolio_returns).cumprod()
        rolling_max = cumulative.expanding().max()
        drawdowns = (cumulative - rolling_max) / rolling_max

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=drawdowns.index,
            y=drawdowns.values,
            fill='tozeroy',
            mode='lines',
            name='Drawdown',
            line=dict(color='#FF0000', width=1),
            fillcolor='rgba(255, 0, 0, 0.2)'
        ))

        fig.update_layout(
            template='plotly_dark',
                font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=250,
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis=dict(gridcolor='#1a1a1a'),
            yaxis=dict(gridcolor='#1a1a1a', tickformat='.1%')
        )

        st.plotly_chart(fig, use_container_width=True)
