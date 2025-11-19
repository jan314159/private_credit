import streamlit as st
import pandas as pd
from datetime import date
# Assuming utils contains the calculation logic
from utils import create_interest_payment_table, create_principal_payment_table, get_repayment_table

# 1. CONFIGURATION
st.set_page_config(layout="wide", page_title="Loan Terms")

# 2. SESSION STATE INITIALIZATION
# We initialize state variables once to handle data persistence across reruns
if "interest_df_" not in st.session_state:
    st.session_state.interest_df_ = pd.DataFrame()
if "principal_df" not in st.session_state:
    st.session_state.principal_df = pd.DataFrame()


# 3. CALLBACKS
# These functions only run when specific inputs change, saving resources
def reset_schedules():
    """Regenerates base schedules when dates or repayment types change."""
    # We use the session state values directly
    st.session_state.interest_df_ = create_interest_payment_table(
        st.session_state.funding_date,
        st.session_state.maturity_date,
        st.session_state.repayment_type
    )
    st.session_state.principal_df = create_principal_payment_table(
        st.session_state.maturity_date
    )


# 4. UI LAYOUT
st.title(":red[_Loan terms_]")

loan_inputs, loan_outputs = st.columns([1, 3])

with loan_inputs:
    st.header(":blue[Loan parameters]")

    # --- Inputs ---
    # Note: We bind values directly to session_state keys
    st.session_state.funding_amount = st.number_input("Loan provided", step=100000, format="%d", value=st.session_state.get("funding_amount", 0))

    # Dynamic Date Constraints: Maturity min_value depends on Funding Date
    col_d1, col_d2 = st.columns(2)

    with col_d1:
         st.session_state.funding_date = st.date_input(
            "Funding date",
             value=st.session_state.get("funding_date", date.today()),
             on_change=reset_schedules  # Trigger update immediately
        )
    with col_d2:
        st.session_state.maturity_date = st.date_input(
            "Maturity date",
            value=st.session_state.get("maturity_date", date.today()),
            on_change=reset_schedules
        )

    # Interest Rate Handling
    rate_input = st.number_input(
        "Interest rate (%)",
        min_value=0.0, max_value=100.0, value=st.session_state.get("interest_rate", 0.0)*100, format="%.2f", step=0.1
    )
    st.session_state.interest_rate = rate_input / 100

    st.session_state.repayment_type = st.selectbox(
        "Interest repayment period",
        ("lump-sum", "annually", "semiannually", "quarterly", "monthly"),
        on_change=reset_schedules
    )

    # --- Data Editors ---
    # Initialize tables on first load if they remain empty
    if st.session_state.interest_df_.empty:
        reset_schedules()

    st.write("Interest Schedule")
    # We edit the dataframe stored in session_state directly
    initial_interest_df = create_interest_payment_table(
        st.session_state.funding_date,
        st.session_state.maturity_date,
        st.session_state.get("repayment_type", "lump-sum"))

    st.session_state.interest_df = st.data_editor(
        initial_interest_df,
        width='stretch',
        num_rows="dynamic"
    )

    initial_principal_df = create_principal_payment_table(st.session_state.maturity_date)

    st.write("Principal Schedule")
    st.session_state.principal_df = st.data_editor(
        initial_principal_df,
        key="editor_principal",
        width='stretch',
        num_rows="dynamic"
    )

with loan_outputs:
    st.header(":blue[Cash flow]")

    # 5. CALCULATION
    # We wrap this to prevent app crashes during intermediate typing states
    if st.session_state.funding_amount > 0:
        try:
            repayment_df = get_repayment_table(
                principal=st.session_state.funding_amount,
                interest=st.session_state.interest_rate,
                interest_df=st.session_state.interest_df,
                principal_df=st.session_state.principal_df,
                maturity_date=st.session_state.maturity_date,
                funding_date=st.session_state.funding_date
            )

            # 6. DISPLAY
            # Optimized column config for readable currency
            currency_fmt = st.column_config.NumberColumn(format="localized", step=1)

            st.dataframe(
                repayment_df,
                width='stretch',
                column_config={
                    col: currency_fmt for col in [
                        "Interest Due (net)", "Interest Paid", "Interest Left",
                        "Principal Paid", "Principal Left", "GC"
                    ]
                }
            )

            # 7. METRICS & CHARTS
            if not repayment_df.empty:
                # Pre-calculate sums to avoid doing it inside the widget calls
                sums = repayment_df[["Interest Due (net)", "Interest Paid", "Principal Paid", "GC"]].sum()

                st.session_state.repayment_df = repayment_df
                # Sidebar
                with st.sidebar:
                    st.header("Summary Metrics")
                    # Chart data: sliced excluding the first row (initial funding)
                    chart_data = repayment_df["Interest Due (net)"].iloc[1:]

                    st.metric("Interest Due", f"{sums['Interest Due (net)']:,.0f}", border=True)
                    st.area_chart(chart_data, height=100, color="#E83E33")

                    st.metric("Interest Paid", f"{sums['Interest Paid']:,.0f}", border=True)
                    st.metric("Principal Paid", f"{sums['Principal Paid']:,.0f}", border=True)
                    st.metric("GC", f"{sums['GC']:,.0f}", border=True)

        except Exception as e:
            st.warning(f"Calculation pending or invalid data: {e}")
    else:
        st.info("Please enter a Loan Amount to generate the Cash Flow.")