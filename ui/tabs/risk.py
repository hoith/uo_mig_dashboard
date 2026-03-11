# ui/tabs/risk.py
import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from calculations.risk import calculate_var_cvar, monte_carlo_simulation
from calculations.positions import calculate_correlation_matrix


def render_risk_tab(portfolio_returns, metrics, total_value, var_confidence,
                    risk_free_rate, prices_df, symbols, hist_var, hist_cvar,
                    param_var, param_cvar, exante):
    """Render the Risk Analytics tab."""
    st.markdown("## Risk Analytics")

    # VaR/CVaR section
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### Historical VaR")
        st.metric(
            f"1-Day VaR ({var_confidence:.0%})",
            f"${abs(hist_var * total_value):,.0f}",
            f"{hist_var:.2%} of portfolio"
        )
        st.metric(
            f"CVaR (Expected Shortfall)",
            f"${abs(hist_cvar * total_value):,.0f}",
            f"{hist_cvar:.2%} of portfolio"
        )

    with col2:
        st.markdown("### Parametric VaR")
        st.metric(
            f"1-Day VaR ({var_confidence:.0%})",
            f"${abs(param_var * total_value):,.0f}",
            f"{param_var:.2%} of portfolio"
        )
        st.metric(
            f"CVaR (Expected Shortfall)",
            f"${abs(param_cvar * total_value):,.0f}",
            f"{param_cvar:.2%} of portfolio"
        )

    with col3:
        st.markdown("### Risk Metrics")
        st.metric("Annualized Volatility", f"{metrics.get('volatility', 0):.1%}")
        st.metric("Skewness", f"{metrics.get('skewness', 0):.2f}")
        st.metric("Kurtosis", f"{metrics.get('kurtosis', 0):.2f}")

    st.markdown("---")

    # Monte Carlo VaR
    st.markdown("### Monte Carlo Simulation")

    col1, col2 = st.columns([2, 1])

    with col1:
        mc_days = st.slider("Simulation Horizon (days)", 21, 252, 63)
        mc_sims = st.selectbox("Number of Simulations", [1000, 5000, 10000], index=1)

    if st.button("RUN MONTE CARLO", type="primary"):
        with st.spinner("Running simulation..."):
            simulations, final_values = monte_carlo_simulation(
                portfolio_returns,
                n_simulations=mc_sims,
                n_days=mc_days,
                initial_value=total_value
            )

            if len(simulations) > 0:
                # MC VaR
                mc_var = np.percentile(final_values, (1 - var_confidence) * 100)
                mc_var_pct = (mc_var - total_value) / total_value
                mc_cvar = final_values[final_values <= mc_var].mean()
                mc_cvar_pct = (mc_cvar - total_value) / total_value

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric(
                        f"MC VaR ({mc_days}d, {var_confidence:.0%})",
                        f"${total_value - mc_var:,.0f}",
                        f"{mc_var_pct:.1%}"
                    )

                with col2:
                    st.metric(
                        f"MC CVaR ({mc_days}d)",
                        f"${total_value - mc_cvar:,.0f}",
                        f"{mc_cvar_pct:.1%}"
                    )

                with col3:
                    median_value = np.median(final_values)
                    st.metric(
                        "Median Outcome",
                        f"${median_value:,.0f}",
                        f"{(median_value - total_value) / total_value:.1%}"
                    )

                # Fan chart
                st.markdown("#### Simulation Fan Chart")

                percentiles = [5, 25, 50, 75, 95]
                percentile_values = np.percentile(simulations, percentiles, axis=0)

                fig = go.Figure()

                # Add percentile bands
                x_range = list(range(mc_days))

                fig.add_trace(go.Scatter(
                    x=x_range + x_range[::-1],
                    y=list(percentile_values[0]) + list(percentile_values[4])[::-1],
                    fill='toself',
                    fillcolor='rgba(255, 102, 0, 0.1)',
                    line=dict(color='rgba(255,255,255,0)'),
                    name='5th-95th %ile'
                ))

                fig.add_trace(go.Scatter(
                    x=x_range + x_range[::-1],
                    y=list(percentile_values[1]) + list(percentile_values[3])[::-1],
                    fill='toself',
                    fillcolor='rgba(255, 102, 0, 0.2)',
                    line=dict(color='rgba(255,255,255,0)'),
                    name='25th-75th %ile'
                ))

                fig.add_trace(go.Scatter(
                    x=x_range,
                    y=percentile_values[2],
                    mode='lines',
                    name='Median',
                    line=dict(color='#FEE123', width=2)
                ))

                fig.update_layout(
                    template='plotly_dark',
                font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    height=400,
                    margin=dict(l=20, r=20, t=20, b=20),
                    xaxis=dict(gridcolor='#1a1a1a', title='Days'),
                    yaxis=dict(gridcolor='#1a1a1a', title='Portfolio Value', tickformat='$,.0f'),
                    legend=dict(orientation='h', yanchor='bottom', y=1.02)
                )

                st.plotly_chart(fig, use_container_width=True)

                # Distribution of final values
                st.markdown("#### Distribution of Final Values")

                fig = go.Figure()

                fig.add_trace(go.Histogram(
                    x=final_values,
                    nbinsx=50,
                    marker_color='#FEE123',
                    opacity=0.7
                ))

                # Add VaR line
                fig.add_vline(
                    x=mc_var,
                    line_dash="dash",
                    line_color="#ef4444",
                    annotation_text=f"VaR: ${mc_var:,.0f}"
                )

                fig.update_layout(
                    template='plotly_dark',
                font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    height=300,
                    margin=dict(l=20, r=20, t=20, b=20),
                    xaxis=dict(gridcolor='#1a1a1a', title='Portfolio Value', tickformat='$,.0f'),
                    yaxis=dict(gridcolor='#1a1a1a', title='Frequency'),
                    showlegend=False
                )

                st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Correlation matrix
    st.markdown("### Correlation Matrix")

    if symbols and len(symbols) > 1:
        corr_matrix = calculate_correlation_matrix(prices_df[symbols])

        if not corr_matrix.empty:
            fig = px.imshow(
                corr_matrix,
                text_auto='.2f',
                color_continuous_scale='RdBu_r',
                aspect='auto',
                zmin=-1,
                zmax=1
            )

            fig.update_layout(
                template='plotly_dark',
                font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=400,
                margin=dict(l=20, r=20, t=20, b=20)
            )

            st.plotly_chart(fig, use_container_width=True)

    # Rolling metrics
    st.markdown("---")
    st.markdown("### Rolling Risk Metrics")

    rolling_window = st.slider("Rolling Window (days)", 21, 126, 63)

    if not portfolio_returns.empty:
        rolling_vol = portfolio_returns.rolling(rolling_window).std() * np.sqrt(252)
        rolling_sharpe = (portfolio_returns.rolling(rolling_window).mean() * 252 - risk_free_rate) / rolling_vol

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1)

        fig.add_trace(
            go.Scatter(x=rolling_vol.index, y=rolling_vol, name='Rolling Vol',
                      line=dict(color='#FEE123')),
            row=1, col=1
        )

        fig.add_trace(
            go.Scatter(x=rolling_sharpe.index, y=rolling_sharpe, name='Rolling Sharpe',
                      line=dict(color='#00C805')),
            row=2, col=1
        )

        fig.update_layout(
            template='plotly_dark',
                font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=400,
            margin=dict(l=20, r=20, t=20, b=20),
            showlegend=True,
            legend=dict(orientation='h', yanchor='bottom', y=1.02)
        )

        fig.update_xaxes(gridcolor='#1a1a1a')
        fig.update_yaxes(gridcolor='#1a1a1a')

        st.plotly_chart(fig, use_container_width=True)
