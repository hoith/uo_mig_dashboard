# ui/tabs/positions.py
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go


def render_positions_tab(position_metrics, position_limit, enable_crp):
    """Render the Positions & Valuation tab."""
    st.markdown("## Positions & Valuation")

    # Editable holdings table
    st.markdown("### Current Holdings")
    st.caption("Edit values directly in the table below")

    if not position_metrics.empty:
        # Format for display
        display_df = position_metrics.copy()

        edited_df = st.data_editor(
            display_df,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Symbol": st.column_config.TextColumn("Symbol", width="small"),
                "Quantity": st.column_config.NumberColumn("Qty", format="%d"),
                "Cost Basis": st.column_config.NumberColumn("Cost Basis", format="$%.2f"),
                "Current Price": st.column_config.NumberColumn("Price", format="$%.2f"),
                "Market Value": st.column_config.NumberColumn("Mkt Value", format="$%,.0f"),
                "Unrealized P&L": st.column_config.NumberColumn("Unreal. P&L", format="$%,.0f"),
                "P&L %": st.column_config.NumberColumn("P&L %", format="%.1f%%"),
                "Weight": st.column_config.NumberColumn("Portfolio Wt", format="%.2f%%"),
                "Index Weight": st.column_config.NumberColumn("Index Wt (IEMG)", format="%.2f%%",
                    help="Constituent weight in IEMG benchmark. Update IEMG_WEIGHTS in config when stale."),
                "Active Weight": st.column_config.NumberColumn("Active Wt", format="%.2f%%",
                    help="Position weight as % of the active (non-IEMG) book. "
                         "Formula: Portfolio Wt / (100 − IEMG Portfolio Wt)."),
                "Volatility": st.column_config.NumberColumn("Vol", format="%.1%"),
                "Beta": st.column_config.NumberColumn("Beta", format="%.2f"),
                "Country": st.column_config.TextColumn("Country", width="small"),
                "CRP (%)": st.column_config.NumberColumn("CRP", format="%.1f%%"),
            }
        )

    st.markdown("---")

    # Position-level charts
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### P&L by Position")
        if not position_metrics.empty:
            fig = px.bar(
                position_metrics.sort_values('Unrealized P&L'),
                x='Symbol',
                y='Unrealized P&L',
                color='Unrealized P&L',
                color_continuous_scale=['#FF0000', '#00C805']
            )

            fig.update_layout(
                template='plotly_dark',
                font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=350,
                margin=dict(l=20, r=20, t=20, b=20),
                xaxis=dict(gridcolor='#1a1a1a'),
                yaxis=dict(gridcolor='#1a1a1a'),
                showlegend=False
            )

            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### Weight vs Position Limit")
        if not position_metrics.empty:
            fig = go.Figure()

            colors = ['#FF0000' if w > position_limit else '#FEE123'
                      for w in position_metrics['Weight']]

            fig.add_trace(go.Bar(
                x=position_metrics['Symbol'],
                y=position_metrics['Weight'],
                marker_color=colors,
                name='Weight'
            ))

            fig.add_hline(
                y=position_limit,
                line_dash="dash",
                line_color="#fbbf24",
                annotation_text=f"Limit: {position_limit}%"
            )

            fig.update_layout(
                template='plotly_dark',
                font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=350,
                margin=dict(l=20, r=20, t=20, b=20),
                xaxis=dict(gridcolor='#1a1a1a'),
                yaxis=dict(gridcolor='#1a1a1a', title='Weight %'),
                showlegend=False
            )

            st.plotly_chart(fig, use_container_width=True)

    # Drift alerts
    if not position_metrics.empty:
        over_limit = position_metrics[position_metrics['Weight'] > position_limit]
        if not over_limit.empty:
            st.warning(f"**POSITION LIMIT BREACHES:** {', '.join(over_limit['Symbol'].tolist())} exceed the {position_limit}% limit")

    # Country Risk Premium analysis
    if enable_crp:
        st.markdown("---")
        st.markdown("### Country Risk Premium Analysis")

        with st.expander("ABOUT COUNTRY RISK PREMIUMS", expanded=False):
            st.markdown("""
            Country Risk Premiums (CRP) represent the additional return required to compensate
            for investing in riskier countries. These estimates are based on Damodaran's methodology
            and consider factors like sovereign credit ratings, currency volatility, and political stability.

            **Adjustment Method:** Returns are adjusted by adding the weighted CRP to the risk-free rate
            in CAPM calculations.
            """)

        if not position_metrics.empty:
            crp_summary = position_metrics.groupby('Country').agg({
                'Market Value': 'sum',
                'CRP (%)': 'first'
            }).reset_index()
            crp_summary['Weight'] = crp_summary['Market Value'] / crp_summary['Market Value'].sum() * 100

            weighted_crp = (crp_summary['Weight'] * crp_summary['CRP (%)']).sum() / 100

            col1, col2 = st.columns([1, 2])

            with col1:
                st.metric("Portfolio Weighted CRP", f"{weighted_crp:.2f}%")
                st.dataframe(crp_summary, use_container_width=True, hide_index=True)

            with col2:
                fig = px.treemap(
                    position_metrics,
                    path=['Country', 'Symbol'],
                    values='Market Value',
                    color='CRP (%)',
                    color_continuous_scale='RdYlGn_r'
                )

                fig.update_layout(
                    template='plotly_dark',
                font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
                    paper_bgcolor='rgba(0,0,0,0)',
                    height=350,
                    margin=dict(l=10, r=10, t=10, b=10)
                )

                st.plotly_chart(fig, use_container_width=True)
