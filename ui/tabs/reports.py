# ui/tabs/reports.py
import streamlit as st
import pandas as pd
from datetime import datetime
from utils.export import export_to_excel, generate_pdf_report


def render_reports_tab(metrics, position_metrics, exante, benchmark,
                       var_confidence, total_value, hist_var, hist_cvar,
                       param_var, param_cvar, portfolio_returns,
                       benchmark_returns, risk_free_rate, holdings_df,
                       transactions_df, stress_results):
    """Render the Reports & Export tab."""
    st.markdown("## Reports & Export")

    # Summary metrics tables
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Return Metrics")

        return_data = {
            'Metric': [
                'TWR (Total)',
                'TWR (Annualized)',
                'MWR/IRR (Total)',
                'MWR/IRR (Annualized)',
                'Simple Return (Total)',
                'Simple Return (Annualized)',
                f'{benchmark} Return (Ann.)',
                'Timing Impact (MWR - TWR)',
            ],
            'Value': [
                f"{metrics.get('twr_total', 0):.2%}",
                f"{metrics.get('twr_annualized', 0):.2%}",
                f"{metrics.get('mwr_total', 0):.2%}",
                f"{metrics.get('mwr_annualized', 0):.2%}",
                f"{metrics.get('simple_total', 0):.2%}",
                f"{metrics.get('simple_annualized', 0):.2%}",
                f"{metrics.get('raw_benchmark_return', 0):.2%}",
                f"{(metrics.get('mwr_annualized', 0) - metrics.get('twr_annualized', 0)):.2%}",
            ],
            'Description': [
                'Manager performance (excl. cash flows)',
                'Annualized TWR',
                'Investor experience (incl. timing)',
                'Annualized MWR',
                'Raw value change (incl. cash flows)',
                'Annualized simple return',
                'Benchmark price return',
                'Positive = good timing',
            ]
        }

        st.dataframe(pd.DataFrame(return_data), use_container_width=True, hide_index=True)

    with col2:
        st.markdown("### Risk-Adjusted Metrics")

        exante_beta_str = f"{exante['exante_beta']:.2f}" if 'exante_beta' in exante else "N/A"
        exante_te_str   = (f"{exante['exante_te']:.2%}" if 'exante_te' in exante
                           else f"N/A (requires IEMG or SPY benchmark)")

        risk_adj_data = {
            'Metric': [
                'Annualized Volatility',
                'Sharpe Ratio',
                'Sortino Ratio',
                'Calmar Ratio',
                'Maximum Drawdown',
                'Beta — Realized (full period)',
                'Beta — Current (trailing 90d)',
                'Beta — Ex-Ante (current composition)',
                'Beta (Ex-Cash, realized)',
                'Alpha (Jensen\'s)',
                'R-Squared',
                'Tracking Error — Realized',
                'Tracking Error — Ex-Ante (current)',
                'Information Ratio',
            ],
            'Value': [
                f"{metrics.get('volatility', 0):.2%}",
                f"{metrics.get('sharpe_ratio', 0):.2f}",
                f"{metrics.get('sortino_ratio', 0):.2f}",
                f"{metrics.get('calmar_ratio', 0):.2f}",
                f"{metrics.get('max_drawdown', 0):.2%}",
                f"{metrics.get('beta', 1):.2f}",
                f"{metrics.get('beta_current_90d', metrics.get('beta_ex_cash', 1)):.2f}",
                exante_beta_str,
                f"{metrics.get('beta_ex_cash', 1):.2f}",
                f"{metrics.get('alpha', 0):.2%}",
                f"{metrics.get('r_squared', 0):.2%}",
                f"{metrics.get('tracking_error', 0):.2%}",
                exante_te_str,
                f"{metrics.get('information_ratio', 0):.2f}",
            ],
            'Description': [
                'Standard deviation (annualized)',
                '(Return - Rf) / Volatility',
                'Return / Downside deviation',
                'Return / Max Drawdown',
                'Peak to trough decline',
                'Cov(r_p, r_b) / Var(r_b) over full selected window — realized',
                'Cov(r_p, r_b) / Var(r_b) over last 90 trading days — current',
                'Σ w_i·β_i — current weights × trailing 252-day position betas',
                'Realized beta excl. cash drag',
                'Excess return vs CAPM',
                'Variance explained by benchmark',
                'StdDev(r_p − r_b) × √252 over selected window',
                '√(w_active′ Σ w_active), current composition',
                'Alpha / Tracking Error',
            ]
        }

        st.dataframe(pd.DataFrame(risk_adj_data), use_container_width=True, hide_index=True)

    st.markdown("---")

    # Additional risk metrics
    st.markdown("### Additional Risk Metrics")
    col1, col2 = st.columns(2)

    with col1:
        risk_data = {
            'Metric': [
                f'VaR ({var_confidence:.0%}, 1-day)',
                'CVaR (Expected Shortfall)',
                'Positive Days %',
                'Best Day',
                'Worst Day',
                'Skewness',
                'Kurtosis'
            ],
            'Value': [
                f"{hist_var:.2%}",
                f"{hist_cvar:.2%}",
                f"{metrics.get('positive_days', 0):.1%}",
                f"{metrics.get('best_day', 0):.2%}",
                f"{metrics.get('worst_day', 0):.2%}",
                f"{metrics.get('skewness', 0):.2f}",
                f"{metrics.get('kurtosis', 0):.2f}",
            ]
        }

        st.dataframe(pd.DataFrame(risk_data), use_container_width=True, hide_index=True)

    with col2:
        # Portfolio composition summary
        st.markdown("**Portfolio Composition**")
        if not position_metrics.empty:
            # Weight column is stored as percentage points (e.g., 10 for 10%), convert to decimal
            cash_weight_pct = position_metrics[position_metrics['Symbol'] == 'CASH']['Weight'].sum() if 'CASH' in position_metrics['Symbol'].values else 0
            securities_weight_pct = 100 - cash_weight_pct
            num_positions = len(position_metrics[position_metrics['Symbol'] != 'CASH'])

            comp_data = {
                'Metric': ['Number of Positions', 'Securities Weight', 'Cash Weight', 'Total Portfolio Value'],
                'Value': [f"{num_positions}", f"{securities_weight_pct:.1f}%", f"{cash_weight_pct:.1f}%", f"${total_value:,.0f}"]
            }
            st.dataframe(pd.DataFrame(comp_data), use_container_width=True, hide_index=True)

    # Create summary_df for export compatibility
    summary_df = pd.DataFrame(return_data)

    st.markdown("---")

    # Basel III-style Risk Metrics (Simplified)
    st.markdown("### Basel III Risk Framework (Simplified)")

    with st.expander("ABOUT BASEL III METRICS", expanded=False):
        st.markdown("""
        This section provides simplified Basel III-style risk metrics:

        - **Risk-Weighted Assets (RWA)**: Assets weighted by risk (using beta as proxy)
        - **Capital Requirement**: Minimum capital buffer (simplified as 8% of RWA)
        - **Liquidity Coverage Ratio (LCR)**: Simplified liquidity measure

        *Note: These are illustrative calculations, not regulatory-compliant figures.*
        """)

    col1, col2, col3 = st.columns(3)

    # Simple RWA calculation (using beta as risk weight proxy)
    if not position_metrics.empty:
        position_metrics['RWA'] = position_metrics['Market Value'] * position_metrics['Beta'].clip(lower=0.5)
        total_rwa = position_metrics['RWA'].sum()

        with col1:
            st.metric(
                "Risk-Weighted Assets",
                f"${total_rwa:,.0f}",
                f"RWA/Total: {total_rwa/total_value:.1%}" if total_value > 0 else "N/A"
            )

        capital_requirement = total_rwa * 0.08
        with col2:
            st.metric(
                "Capital Requirement (8%)",
                f"${capital_requirement:,.0f}",
                "Tier 1 Capital Buffer"
            )

        # Simplified LCR (assume all equity is liquid)
        lcr = total_value / capital_requirement if capital_requirement > 0 else 0
        with col3:
            st.metric(
                "Liquidity Coverage (Simplified)",
                f"{lcr:.1f}x",
                ">=1.0 required" if lcr >= 1 else "BELOW THRESHOLD"
            )

    st.markdown("---")

    # Export options
    st.markdown("### Export Reports")

    col1, col2, col3 = st.columns(3)

    with col1:
        # Excel export
        excel_data = export_to_excel({
            'Summary': summary_df,
            'Risk Metrics': pd.DataFrame(risk_data),
            'Holdings': position_metrics,
            'Performance Metrics': pd.DataFrame([metrics])
        })

        st.download_button(
            "DOWNLOAD EXCEL REPORT",
            excel_data,
            file_name=f"portfolio_report_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )

    with col2:
        # CSV export
        full_report = pd.concat([
            summary_df.assign(Category='Performance'),
            pd.DataFrame(risk_data).assign(Category='Risk')
        ], ignore_index=True)

        csv_data = full_report.to_csv(index=False)

        st.download_button(
            "DOWNLOAD CSV REPORT",
            csv_data,
            file_name=f"portfolio_metrics_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

    with col3:
        # PDF export (if reportlab available)
        pdf_data = generate_pdf_report(metrics, st.session_state.holdings, None)

        if pdf_data:
            st.download_button(
                "DOWNLOAD PDF REPORT",
                pdf_data,
                file_name=f"portfolio_report_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf"
            )
        else:
            st.info("PDF export requires reportlab. Install with: pip install reportlab")

    st.markdown("---")

    # Transaction history
    st.markdown("### Transaction History")

    if not st.session_state.transactions.empty:
        st.dataframe(
            st.session_state.transactions.sort_values('date', ascending=False),
            use_container_width=True,
            hide_index=True
        )

        tx_csv = st.session_state.transactions.to_csv(index=False)
        st.download_button(
            "DOWNLOAD TRANSACTIONS",
            tx_csv,
            file_name="transactions_export.csv",
            mime="text/csv"
        )
