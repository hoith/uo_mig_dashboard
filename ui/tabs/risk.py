# ui/tabs/risk.py
import streamlit as st
import numpy as np
import pandas as pd
import scipy.stats as stats
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from calculations.risk import calculate_var_cvar, monte_carlo_simulation
from calculations.positions import calculate_correlation_matrix


def _find_drawdown_periods(returns, top_n=8):
    """Return a DataFrame of the worst historical drawdown periods."""
    cum = (1 + returns).cumprod()
    roll_max = cum.expanding().max()
    dd = (cum - roll_max) / roll_max

    periods, in_dd, start, trough_val, trough_dt = [], False, None, 0, None
    for dt, val in dd.items():
        if not in_dd and val < -0.001:
            in_dd, start, trough_val, trough_dt = True, dt, val, dt
        elif in_dd and val < 0:
            if val < trough_val:
                trough_val, trough_dt = val, dt
        elif in_dd and val >= -0.001:
            periods.append({
                'Start': start.strftime('%Y-%m-%d'),
                'Trough': trough_dt.strftime('%Y-%m-%d'),
                'Recovery': dt.strftime('%Y-%m-%d'),
                'Depth': trough_val,
                'Duration (days)': (dt - start).days,
                'Recovery (days)': (dt - trough_dt).days,
            })
            in_dd = False

    if in_dd:
        periods.append({
            'Start': start.strftime('%Y-%m-%d'),
            'Trough': trough_dt.strftime('%Y-%m-%d'),
            'Recovery': '(ongoing)',
            'Depth': trough_val,
            'Duration (days)': (returns.index[-1] - start).days,
            'Recovery (days)': '—',
        })

    if not periods:
        return pd.DataFrame()

    df = pd.DataFrame(periods).sort_values('Depth').head(top_n).reset_index(drop=True)
    df['Depth'] = df['Depth'].map('{:.2%}'.format)
    return df


def render_risk_tab(portfolio_returns, metrics, total_value, var_confidence,
                    risk_free_rate, prices_df, symbols, hist_var, hist_cvar,
                    param_var, param_cvar, exante, benchmark_returns=None):
    """Render the Risk Analytics tab."""
    st.markdown("## Risk Analytics")

    # -------------------------------------------------------------------------
    # VaR / CVaR Summary
    # -------------------------------------------------------------------------
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### Historical VaR")
        st.metric(
            f"1-Day VaR ({var_confidence:.0%})",
            f"${abs(hist_var * total_value):,.0f}",
            f"{hist_var:.2%} of portfolio"
        )
        st.metric(
            "CVaR (Expected Shortfall)",
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
            "CVaR (Expected Shortfall)",
            f"${abs(param_cvar * total_value):,.0f}",
            f"{param_cvar:.2%} of portfolio"
        )

    with col3:
        st.markdown("### Risk Metrics")
        st.metric("Annualised Volatility", f"{metrics.get('volatility', 0):.1%}")
        st.metric("Skewness", f"{metrics.get('skewness', 0):.2f}")
        st.metric("Kurtosis (excess)", f"{metrics.get('kurtosis', 0):.2f}")

    st.markdown("---")

    # -------------------------------------------------------------------------
    # Return Distribution — always visible, no button needed
    # -------------------------------------------------------------------------
    st.markdown("### Return Distribution")

    if not portfolio_returns.empty:
        _mu    = portfolio_returns.mean()
        _sigma = portfolio_returns.std()

        _x_norm = np.linspace(portfolio_returns.min(), portfolio_returns.max(), 300)
        _y_norm = stats.norm.pdf(_x_norm, _mu, _sigma)

        fig = go.Figure()

        fig.add_trace(go.Histogram(
            x=portfolio_returns.values,
            nbinsx=60,
            marker_color='#FEE123',
            opacity=0.65,
            name='Actual Returns',
            histnorm='probability density'
        ))

        fig.add_trace(go.Scatter(
            x=_x_norm, y=_y_norm,
            mode='lines', name='Normal Fit',
            line=dict(color='#00C805', width=2)
        ))

        fig.add_vline(
            x=hist_var, line_dash='dash', line_color='#FF4444',
            annotation_text=f'VaR {var_confidence:.0%}: {hist_var:.2%}',
            annotation_font_color='#FF4444', annotation_position='top right'
        )
        fig.add_vline(
            x=hist_cvar, line_dash='dot', line_color='#FF8800',
            annotation_text=f'CVaR: {hist_cvar:.2%}',
            annotation_font_color='#FF8800', annotation_position='top left'
        )

        fig.update_layout(
            template='plotly_dark',
            font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            height=300,
            margin=dict(l=20, r=20, t=30, b=20),
            xaxis=dict(gridcolor='#1a1a1a', title='Daily Return', tickformat='.2%'),
            yaxis=dict(gridcolor='#1a1a1a', title='Density'),
            legend=dict(orientation='h', yanchor='bottom', y=1.02),
            barmode='overlay'
        )

        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # -------------------------------------------------------------------------
    # Monte Carlo Simulation
    # -------------------------------------------------------------------------
    st.markdown("### Monte Carlo Simulation")

    col1, col2 = st.columns([2, 1])
    with col1:
        mc_days = st.slider("Simulation Horizon (days)", 21, 252, 63)
        mc_sims = st.selectbox("Number of Simulations", [1000, 5000, 10000], index=1)

    if st.button("RUN MONTE CARLO", type="primary"):
        with st.spinner("Running simulation..."):
            simulations, final_values = monte_carlo_simulation(
                portfolio_returns, n_simulations=mc_sims,
                n_days=mc_days, initial_value=total_value
            )

            if len(simulations) > 0:
                mc_var      = np.percentile(final_values, (1 - var_confidence) * 100)
                mc_var_pct  = (mc_var - total_value) / total_value
                mc_cvar     = final_values[final_values <= mc_var].mean()
                mc_cvar_pct = (mc_cvar - total_value) / total_value

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(f"MC VaR ({mc_days}d, {var_confidence:.0%})",
                              f"${total_value - mc_var:,.0f}", f"{mc_var_pct:.1%}")
                with col2:
                    st.metric(f"MC CVaR ({mc_days}d)",
                              f"${total_value - mc_cvar:,.0f}", f"{mc_cvar_pct:.1%}")
                with col3:
                    median_value = np.median(final_values)
                    st.metric("Median Outcome", f"${median_value:,.0f}",
                              f"{(median_value - total_value) / total_value:.1%}")

                # Fan chart
                st.markdown("#### Simulation Fan Chart")
                percentiles = [5, 25, 50, 75, 95]
                pct_vals    = np.percentile(simulations, percentiles, axis=0)
                x_range     = list(range(mc_days))

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=x_range + x_range[::-1],
                    y=list(pct_vals[0]) + list(pct_vals[4])[::-1],
                    fill='toself', fillcolor='rgba(255,102,0,0.1)',
                    line=dict(color='rgba(255,255,255,0)'), name='5th–95th %ile'
                ))
                fig.add_trace(go.Scatter(
                    x=x_range + x_range[::-1],
                    y=list(pct_vals[1]) + list(pct_vals[3])[::-1],
                    fill='toself', fillcolor='rgba(255,102,0,0.2)',
                    line=dict(color='rgba(255,255,255,0)'), name='25th–75th %ile'
                ))
                fig.add_trace(go.Scatter(
                    x=x_range, y=pct_vals[2],
                    mode='lines', name='Median',
                    line=dict(color='#FEE123', width=2)
                ))
                fig.update_layout(
                    template='plotly_dark',
                    font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    height=400, margin=dict(l=20, r=20, t=20, b=20),
                    xaxis=dict(gridcolor='#1a1a1a', title='Days'),
                    yaxis=dict(gridcolor='#1a1a1a', title='Portfolio Value', tickformat='$,.0f'),
                    legend=dict(orientation='h', yanchor='bottom', y=1.02)
                )
                st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # -------------------------------------------------------------------------
    # Correlation Matrix  |  Portfolio vs Benchmark Scatter
    # -------------------------------------------------------------------------
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Correlation Matrix")
        if symbols and len(symbols) > 1:
            corr_matrix = calculate_correlation_matrix(prices_df[symbols])
            if not corr_matrix.empty:
                fig = px.imshow(
                    corr_matrix, text_auto='.2f',
                    color_continuous_scale='RdBu_r',
                    aspect='auto', zmin=-1, zmax=1
                )
                fig.update_layout(
                    template='plotly_dark',
                    font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    height=400, margin=dict(l=20, r=20, t=20, b=20)
                )
                st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### Portfolio vs Benchmark")
        if (benchmark_returns is not None and not benchmark_returns.empty
                and not portfolio_returns.empty):
            _sc = pd.concat([portfolio_returns, benchmark_returns], axis=1, join='inner')
            _sc.columns = ['Portfolio', 'Benchmark']

            _x = _sc['Benchmark'].values
            _y = _sc['Portfolio'].values
            _slope, _intercept = np.polyfit(_x, _y, 1)
            _xlim = max(abs(_x.min()), abs(_x.max()))
            _xline = np.array([-_xlim, _xlim])
            _yline = _slope * _xline + _intercept

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=_sc['Benchmark'], y=_sc['Portfolio'],
                mode='markers', name='Daily Returns',
                marker=dict(color='#FEE123', size=4, opacity=0.5)
            ))
            fig.add_trace(go.Scatter(
                x=_xline, y=_yline,
                mode='lines', name=f'Regression (β={_slope:.2f})',
                line=dict(color='#00C805', width=2)
            ))
            fig.add_trace(go.Scatter(
                x=[-_xlim, _xlim], y=[-_xlim, _xlim],
                mode='lines', name='1:1',
                line=dict(color='#444444', width=1, dash='dash')
            ))
            fig.update_layout(
                template='plotly_dark',
                font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                height=400, margin=dict(l=20, r=20, t=20, b=20),
                xaxis=dict(gridcolor='#1a1a1a', title='Benchmark Daily Return', tickformat='.1%'),
                yaxis=dict(gridcolor='#1a1a1a', title='Portfolio Daily Return', tickformat='.1%'),
                legend=dict(orientation='h', yanchor='bottom', y=1.02)
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # -------------------------------------------------------------------------
    # Rolling Risk Metrics (Vol, Sharpe, Beta)
    # -------------------------------------------------------------------------
    st.markdown("### Rolling Risk Metrics")
    rolling_window = st.slider("Rolling Window (days)", 21, 126, 63)

    if not portfolio_returns.empty:
        rolling_vol    = portfolio_returns.rolling(rolling_window).std() * np.sqrt(252)
        rolling_sharpe = (portfolio_returns.rolling(rolling_window).mean() * 252
                          - risk_free_rate) / rolling_vol

        _has_beta = benchmark_returns is not None and not benchmark_returns.empty
        n_rows    = 3 if _has_beta else 2
        titles    = ['Rolling Volatility (Ann.)', 'Rolling Sharpe']
        if _has_beta:
            titles.append('Rolling Beta')

        fig = make_subplots(rows=n_rows, cols=1, shared_xaxes=True,
                            vertical_spacing=0.08, subplot_titles=titles)

        fig.add_trace(go.Scatter(x=rolling_vol.index, y=rolling_vol,
                                 name='Rolling Vol', line=dict(color='#FEE123')),
                      row=1, col=1)
        fig.add_trace(go.Scatter(x=rolling_sharpe.index, y=rolling_sharpe,
                                 name='Rolling Sharpe', line=dict(color='#00C805')),
                      row=2, col=1)

        if _has_beta:
            _rb = pd.concat([portfolio_returns, benchmark_returns], axis=1, join='inner')
            _rb.columns = ['p', 'b']
            rolling_beta = (_rb['p'].rolling(rolling_window).cov(_rb['b'])
                            / _rb['b'].rolling(rolling_window).var())
            fig.add_trace(go.Scatter(x=rolling_beta.index, y=rolling_beta,
                                     name='Rolling Beta', line=dict(color='#4488FF')),
                          row=3, col=1)
            fig.add_hline(y=1.0, line_dash='dash', line_color='#444444', row=3, col=1)

        fig.update_layout(
            template='plotly_dark',
            font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            height=140 * n_rows + 60,
            margin=dict(l=20, r=20, t=40, b=20),
            showlegend=False
        )
        fig.update_xaxes(gridcolor='#1a1a1a')
        fig.update_yaxes(gridcolor='#1a1a1a')
        fig.update_yaxes(tickformat='.1%', row=1, col=1)
        fig.update_yaxes(tickformat='.2f', row=2, col=1)
        if _has_beta:
            fig.update_yaxes(tickformat='.2f', row=3, col=1)

        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # -------------------------------------------------------------------------
    # Historical Drawdown Periods Table
    # -------------------------------------------------------------------------
    st.markdown("### Historical Drawdown Periods")
    if not portfolio_returns.empty:
        dd_df = _find_drawdown_periods(portfolio_returns)
        if not dd_df.empty:
            st.dataframe(dd_df, use_container_width=True, hide_index=True)
        else:
            st.info("No significant drawdown periods found in this date range.")
