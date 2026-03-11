# ui/tabs/transactions.py
import streamlit as st
import pandas as pd
import plotly.express as px
from calculations.portfolio import calculate_cash_from_transactions


def render_transactions_tab():
    """Render the Transaction History tab. Reads from st.session_state."""
    st.markdown("## Transaction History")

    if st.session_state.transactions is not None and not st.session_state.transactions.empty:
        txn_df = st.session_state.transactions.copy()

        # Summary metrics - Row 1
        col1, col2, col3, col4 = st.columns(4)

        total_buys = len(txn_df[txn_df['side'] == 'BUY'])
        total_sells = len(txn_df[txn_df['side'] == 'SELL'])
        total_withdrawals = len(txn_df[txn_df['side'].isin(['WITHDRAWAL', 'REBALANCE'])])
        total_deposits = len(txn_df[txn_df['side'] == 'DEPOSIT'])
        total_fees = txn_df['fees'].sum() if 'fees' in txn_df.columns else 0

        # Calculate total buy/sell values
        buy_txns = txn_df[txn_df['side'] == 'BUY']
        sell_txns = txn_df[txn_df['side'] == 'SELL']
        withdrawal_txns = txn_df[txn_df['side'].isin(['WITHDRAWAL', 'REBALANCE'])]
        deposit_txns = txn_df[txn_df['side'] == 'DEPOSIT']

        total_buy_value = (buy_txns['quantity'] * buy_txns['price']).sum() if not buy_txns.empty else 0
        total_sell_value = (sell_txns['quantity'] * sell_txns['price']).sum() if not sell_txns.empty else 0
        total_withdrawal_value = (withdrawal_txns['quantity'] * withdrawal_txns['price'].fillna(1)).sum() if not withdrawal_txns.empty else 0
        total_deposit_value = (deposit_txns['quantity'] * deposit_txns['price'].fillna(1)).sum() if not deposit_txns.empty else 0

        with col1:
            st.metric("Total Transactions", len(txn_df))
        with col2:
            st.metric("Buy Orders", total_buys, f"${total_buy_value:,.0f}")
        with col3:
            st.metric("Sell Orders", total_sells, f"${total_sell_value:,.0f}")
        with col4:
            st.metric("Total Fees", f"${total_fees:,.2f}")

        # Summary metrics - Row 2 (Cash movements)
        if total_withdrawals > 0 or total_deposits > 0:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Withdrawals/Rebalance", total_withdrawals, f"-${total_withdrawal_value:,.0f}", delta_color="inverse")
            with col2:
                st.metric("Deposits", total_deposits, f"+${total_deposit_value:,.0f}")
            with col3:
                net_cash_movement = total_deposit_value - total_withdrawal_value
                st.metric("Net Cash Movement", f"${net_cash_movement:,.0f}")
            with col4:
                pass  # Empty column for alignment

        st.markdown("---")

        # Transaction filters
        col1, col2, col3 = st.columns(3)

        # Get all unique transaction types in the data
        all_sides = txn_df['side'].unique().tolist()
        default_sides = [s for s in all_sides if s in ['BUY', 'SELL', 'WITHDRAWAL', 'REBALANCE', 'DEPOSIT']]

        with col1:
            side_filter = st.multiselect(
                "Filter by Action",
                options=all_sides,
                default=default_sides if default_sides else all_sides
            )

        with col2:
            symbols_in_txns = txn_df['symbol'].unique().tolist()
            symbol_filter = st.multiselect(
                "Filter by Symbol",
                options=symbols_in_txns,
                default=symbols_in_txns
            )

        with col3:
            sort_order = st.selectbox(
                "Sort by Date",
                options=['Newest First', 'Oldest First'],
                index=0
            )

        # Apply filters
        filtered_txns = txn_df[
            (txn_df['side'].isin(side_filter)) &
            (txn_df['symbol'].isin(symbol_filter))
        ].copy()

        # Sort
        ascending = sort_order == 'Oldest First'
        filtered_txns = filtered_txns.sort_values('date', ascending=ascending)

        # Calculate transaction value (handle NaN prices for cash transactions)
        filtered_txns['price'] = filtered_txns['price'].fillna(1)
        filtered_txns['fees'] = filtered_txns['fees'].fillna(0)
        filtered_txns['value'] = filtered_txns['quantity'] * filtered_txns['price']

        # Display table
        st.markdown("### All Transactions")

        display_txns = filtered_txns.copy()
        display_txns['date'] = pd.to_datetime(display_txns['date']).dt.strftime('%Y-%m-%d')

        st.dataframe(
            display_txns[['date', 'symbol', 'side', 'quantity', 'price', 'fees', 'value']],
            use_container_width=True,
            column_config={
                "date": st.column_config.TextColumn("Date"),
                "symbol": st.column_config.TextColumn("Symbol"),
                "side": st.column_config.TextColumn("Action"),
                "quantity": st.column_config.NumberColumn("Shares/Amount", format="%.2f"),
                "price": st.column_config.NumberColumn("Price", format="$%.2f"),
                "fees": st.column_config.NumberColumn("Fees", format="$%.2f"),
                "value": st.column_config.NumberColumn("Value", format="$%,.2f"),
            },
            hide_index=True
        )

        st.markdown("---")

        # Transaction charts
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### Transactions by Symbol")
            txn_by_symbol = txn_df.groupby(['symbol', 'side']).agg({
                'quantity': 'sum',
                'price': 'mean'
            }).reset_index()
            txn_by_symbol['price'] = txn_by_symbol['price'].fillna(1)
            txn_by_symbol['value'] = txn_by_symbol['quantity'] * txn_by_symbol['price']

            fig = px.bar(
                txn_by_symbol,
                x='symbol',
                y='value',
                color='side',
                barmode='group',
                color_discrete_map={
                    'BUY': '#00C805',
                    'SELL': '#FF0000',
                    'WITHDRAWAL': '#FFD700',
                    'REBALANCE': '#FF9900',
                    'DEPOSIT': '#4488FF'
                }
            )
            fig.update_layout(
                template='plotly_dark',
                font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=350,
                margin=dict(l=20, r=20, t=20, b=20),
                xaxis=dict(gridcolor='#1a1a1a'),
                yaxis=dict(gridcolor='#1a1a1a', title='Value ($)'),
                legend=dict(title='Action')
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("### Transaction Timeline")
            txn_timeline = txn_df.copy()
            txn_timeline['value'] = txn_timeline['quantity'] * txn_timeline['price'].fillna(1)
            txn_timeline['value'] = txn_timeline.apply(
                lambda x: x['value'] if x['side'] in ['BUY', 'DEPOSIT'] else -x['value'], axis=1
            )

            fig = px.scatter(
                txn_timeline,
                x='date',
                y='value',
                color='side',
                size=abs(txn_timeline['value']),
                hover_data=['symbol', 'quantity', 'price'],
                color_discrete_map={
                    'BUY': '#00C805',
                    'SELL': '#FF0000',
                    'WITHDRAWAL': '#FFD700',
                    'REBALANCE': '#FF9900',
                    'DEPOSIT': '#4488FF'
                }
            )
            fig.update_layout(
                template='plotly_dark',
                font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=350,
                margin=dict(l=20, r=20, t=20, b=20),
                xaxis=dict(gridcolor='#1a1a1a', title='Date'),
                yaxis=dict(gridcolor='#1a1a1a', title='Value ($)'),
                legend=dict(title='Action')
            )
            st.plotly_chart(fig, use_container_width=True)

        # Cash flow summary
        st.markdown("---")
        st.markdown("### Cash Flow Summary")

        # Calculate cash flows by month
        txn_cashflow = txn_df.copy()
        txn_cashflow['date'] = pd.to_datetime(txn_cashflow['date'])
        txn_cashflow['month'] = txn_cashflow['date'].dt.to_period('M')

        def calc_cash_flow(row):
            qty = float(row.get('quantity', 0) or 0)
            price = float(row.get('price', 0) or 1)
            fees = float(row.get('fees', 0) or 0)
            side = str(row.get('side', '')).upper()

            if side == 'SELL':
                return qty * price - fees
            elif side == 'BUY':
                return -(qty * price + fees)
            elif side in ['WITHDRAWAL', 'REBALANCE']:
                return -(qty * price)  # Cash leaving portfolio
            elif side == 'DEPOSIT':
                return qty * price  # Cash entering portfolio
            return 0

        txn_cashflow['cash_flow'] = txn_cashflow.apply(calc_cash_flow, axis=1)

        monthly_cf = txn_cashflow.groupby('month')['cash_flow'].sum().reset_index()
        monthly_cf['month'] = monthly_cf['month'].astype(str)

        fig = px.bar(
            monthly_cf,
            x='month',
            y='cash_flow',
            color='cash_flow',
            color_continuous_scale=['#FF0000', '#FFD700', '#00C805']
        )
        fig.update_layout(
            template='plotly_dark',
                font=dict(family='JetBrains Mono, monospace', color='#E0E0E0', size=11),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=300,
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis=dict(gridcolor='#1a1a1a', title='Month'),
            yaxis=dict(gridcolor='#1a1a1a', title='Net Cash Flow ($)'),
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)

        # Current cash balance (initial_cash from holdings file)
        initial_cash = st.session_state.get('initial_cash', 0.0)
        current_cash, total_withdrawals, total_deposits = calculate_cash_from_transactions(txn_df, initial_cash)

        # Display cash summary
        st.markdown("---")
        st.markdown("### Cash Balance Summary")
        cash_col1, cash_col2, cash_col3, cash_col4 = st.columns(4)
        with cash_col1:
            st.metric("Starting Cash", f"${initial_cash:,.2f}")
        with cash_col2:
            st.metric("Total Withdrawals", f"${total_withdrawals:,.2f}", delta=f"-${total_withdrawals:,.2f}" if total_withdrawals > 0 else None, delta_color="inverse")
        with cash_col3:
            st.metric("Total Deposits", f"${total_deposits:,.2f}", delta=f"+${total_deposits:,.2f}" if total_deposits > 0 else None)
        with cash_col4:
            st.metric("Current Cash", f"${current_cash:,.2f}")

    else:
        st.warning("No transactions loaded. Upload a transactions CSV or check your data files.")
