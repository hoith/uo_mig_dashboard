# ui/tabs/stress.py
import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from calculations.risk import run_stress_tests
from calculations.optimization import optimize_portfolio, generate_rebalance_transactions


def render_stress_tab(portfolio_returns, metrics, total_value, position_metrics,
                      prices_df, current_symbols, symbols, risk_free_rate,
                      holdings_df):
    """Render the Stress Testing & Rebalancing tab.

    Args:
        current_symbols: Active position symbols only (non-cash, non-zero weight)
                         Used for optimization and efficient frontier.
        symbols: Full historical symbol list. Used for stress tests.
    """
    st.markdown("## Stress Testing & Rebalancing")

    # Stress Testing
    st.markdown("### STRESS TESTING")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("**Custom Scenario**")

        custom_shock = st.slider("Market-wide shock (%)", -60, 20, -20)
        tech_shock = st.slider("Tech sector shock (%)", -60, 20, -25)

        custom_scenario = {
            'Custom Scenario': {
                'market': custom_shock / 100,
                'tech': tech_shock / 100,
            }
        }

    if st.button("RUN STRESS TESTS", type="primary"):
        with st.spinner("Running stress scenarios..."):
            stress_results = run_stress_tests(
                st.session_state.holdings,
                prices_df[symbols]
            )

            # Add custom scenario
            custom_results = run_stress_tests(
                st.session_state.holdings,
                prices_df[symbols],
                custom_scenario
            )

            all_results = pd.concat([stress_results, custom_results], ignore_index=True)

            with col2:
                st.markdown("**Stress Test Results**")

                fig = px.bar(
                    all_results,
                    y='Scenario',
                    x='Portfolio Loss (%)',
                    orientation='h',
                    color='Portfolio Loss (%)',
                    color_continuous_scale=['#FF0000', '#FFD700', '#00C805']
                )

                fig.update_layout(
                    template='plotly_dark',
                font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    height=350,
                    margin=dict(l=20, r=20, t=20, b=20),
                    xaxis=dict(gridcolor='#1a1a1a', title='Loss %'),
                    yaxis=dict(gridcolor='#1a1a1a'),
                    showlegend=False
                )

                st.plotly_chart(fig, use_container_width=True)

            # Results table
            st.dataframe(
                all_results.style.format({
                    'Portfolio Loss ($)': '${:,.0f}',
                    'Portfolio Loss (%)': '{:.1f}%'
                }).background_gradient(
                    subset=['Portfolio Loss (%)'],
                    cmap='RdYlGn_r'
                ),
                use_container_width=True,
                hide_index=True
            )

    st.markdown("---")

    # Rebalancing
    st.markdown("### PORTFOLIO REBALANCING")

    col1, col2 = st.columns(2)

    with col1:
        rebalance_method = st.selectbox(
            "Optimization Method",
            ['max_sharpe', 'min_variance', 'risk_parity'],
            format_func=lambda x: {
                'max_sharpe': 'Maximum Sharpe Ratio',
                'min_variance': 'Minimum Variance',
                'risk_parity': 'Risk Parity'
            }[x]
        )

        max_weight = st.slider("Max Weight per Position (%)", 10, 50, 25)
        min_weight = st.slider("Min Weight per Position (%)", 0, 10, 2)

    if st.button("OPTIMIZE PORTFOLIO", type="primary"):
        with st.spinner("Running optimization..."):
            # BUG FIX: use current_symbols (active positions only) instead of symbols
            # (full historical list) to avoid KeyError on delisted/sold tickers
            returns_df = prices_df[current_symbols].pct_change().dropna()

            optimization_result = optimize_portfolio(
                returns_df,
                method=rebalance_method,
                risk_free_rate=risk_free_rate,
                max_weight=max_weight / 100,
                min_weight=min_weight / 100
            )

            if optimization_result.get('success'):
                with col2:
                    st.markdown("**Optimal Portfolio Metrics**")

                    st.metric(
                        "Expected Return",
                        f"{optimization_result['expected_return']:.1%}"
                    )
                    st.metric(
                        "Expected Volatility",
                        f"{optimization_result['expected_volatility']:.1%}"
                    )
                    st.metric(
                        "Sharpe Ratio",
                        f"{optimization_result['sharpe_ratio']:.2f}"
                    )

                st.markdown("#### Optimal Weights")

                weights_df = pd.DataFrame([
                    {'Symbol': s, 'Optimal Weight': w * 100}
                    for s, w in optimization_result['weights'].items()
                ])

                # Compare with current
                current_weights = position_metrics[['Symbol', 'Weight']].copy()
                current_weights.columns = ['Symbol', 'Current Weight']

                comparison = weights_df.merge(current_weights, on='Symbol', how='outer').fillna(0)
                comparison['Change'] = comparison['Optimal Weight'] - comparison['Current Weight']

                fig = go.Figure()

                fig.add_trace(go.Bar(
                    name='Current',
                    x=comparison['Symbol'],
                    y=comparison['Current Weight'],
                    marker_color='#666666'
                ))

                fig.add_trace(go.Bar(
                    name='Optimal',
                    x=comparison['Symbol'],
                    y=comparison['Optimal Weight'],
                    marker_color='#FEE123'
                ))

                fig.update_layout(
                    template='plotly_dark',
                font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    height=350,
                    margin=dict(l=20, r=20, t=20, b=20),
                    xaxis=dict(gridcolor='#1a1a1a'),
                    yaxis=dict(gridcolor='#1a1a1a', title='Weight %'),
                    barmode='group',
                    legend=dict(orientation='h', yanchor='bottom', y=1.02)
                )

                st.plotly_chart(fig, use_container_width=True)

                # Generate rebalance transactions
                st.markdown("#### Rebalancing Transactions")

                current_holdings = st.session_state.holdings.set_index('symbol')['quantity'].to_dict()

                rebalance_txns = generate_rebalance_transactions(
                    current_holdings,
                    optimization_result['weights'],
                    prices_df[current_symbols],
                    total_value
                )

                if not rebalance_txns.empty:
                    st.dataframe(
                        rebalance_txns.style.format({
                            'Est. Price': '${:.2f}',
                            'Est. Value': '${:,.0f}',
                            'Current Weight': '{:.1f}%',
                            'Target Weight': '{:.1f}%'
                        }),
                        use_container_width=True,
                        hide_index=True
                    )

                    # Export button
                    rebalance_csv = rebalance_txns.to_csv(index=False)
                    st.download_button(
                        "DOWNLOAD REBALANCE ORDERS",
                        rebalance_csv,
                        file_name="rebalance_orders.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("Portfolio is already optimally balanced!")
            else:
                st.error("Optimization failed. Try adjusting constraints.")

    # Efficient Frontier
    st.markdown("---")
    st.markdown("### Efficient Frontier")

    if st.button("GENERATE EFFICIENT FRONTIER"):
        with st.spinner("Calculating efficient frontier..."):
            # BUG FIX: use current_symbols (active positions only) instead of symbols
            # (full historical list) to avoid KeyError on delisted/sold tickers
            returns_df = prices_df[current_symbols].pct_change().dropna()
            mean_returns = returns_df.mean() * 252
            cov_matrix = returns_df.cov() * 252

            # Generate frontier points
            n_portfolios = 100
            results = []

            target_returns = np.linspace(mean_returns.min(), mean_returns.max(), n_portfolios)

            for target in target_returns:
                try:
                    result = optimize_portfolio(
                        returns_df,
                        method='min_variance',
                        target_return=target,
                        max_weight=0.5,
                        min_weight=0.0
                    )
                    if result.get('success'):
                        results.append({
                            'Return': result['expected_return'],
                            'Volatility': result['expected_volatility'],
                            'Sharpe': result['sharpe_ratio']
                        })
                except:
                    continue

            if results:
                frontier_df = pd.DataFrame(results)

                fig = go.Figure()

                fig.add_trace(go.Scatter(
                    x=frontier_df['Volatility'],
                    y=frontier_df['Return'],
                    mode='lines',
                    name='Efficient Frontier',
                    line=dict(color='#FEE123', width=3)
                ))

                # Add current portfolio
                fig.add_trace(go.Scatter(
                    x=[metrics.get('volatility', 0)],
                    y=[metrics.get('annualized_return', 0)],
                    mode='markers',
                    name='Current Portfolio',
                    marker=dict(color='#FFD700', size=15, symbol='star')
                ))

                # Add individual assets
                for symbol in current_symbols:
                    asset_returns = returns_df[symbol]
                    asset_vol = asset_returns.std() * np.sqrt(252)
                    asset_ret = asset_returns.mean() * 252

                    fig.add_trace(go.Scatter(
                        x=[asset_vol],
                        y=[asset_ret],
                        mode='markers+text',
                        name=symbol,
                        text=[symbol],
                        textposition='top center',
                        marker=dict(size=10)
                    ))

                fig.update_layout(
                    template='plotly_dark',
                font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    height=500,
                    margin=dict(l=20, r=20, t=20, b=20),
                    xaxis=dict(gridcolor='#1a1a1a', title='Volatility', tickformat='.1%'),
                    yaxis=dict(gridcolor='#1a1a1a', title='Return', tickformat='.1%'),
                    legend=dict(orientation='h', yanchor='bottom', y=1.02)
                )

                st.plotly_chart(fig, use_container_width=True)
