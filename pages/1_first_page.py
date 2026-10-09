from datetime import date

import streamlit as st
from utils import create_interest_payment_table, create_principal_payment_table, get_repayment_table
from state import keep_inputs

# 1. CONFIGURATION
st.set_page_config(layout="wide", page_title="Loan Terms")

# 2. SESSION STATE
# Keeps every input (on this and the other pages) when switching pages
keep_inputs()


# 3. CALLBACKS
def reset_schedules():
    """Regenerates base schedules when dates or repayment types change, discarding edits."""
    st.session_state.interest_base = create_interest_payment_table(
        st.session_state.funding_date,
        st.session_state.maturity_date,
        st.session_state.repayment_type
    )
    st.session_state.principal_base = create_principal_payment_table(
        st.session_state.maturity_date
    )
    st.session_state.interest_df = st.session_state.interest_base
    st.session_state.principal_df = st.session_state.principal_base
    st.session_state.pop("editor_interest", None)
    st.session_state.pop("editor_principal", None)


if "interest_base" not in st.session_state:
    reset_schedules()

# Editor edits are dropped when leaving the page, so on return start from the last edited tables
if "editor_interest" not in st.session_state:
    st.session_state.interest_base = st.session_state.interest_df
if "editor_principal" not in st.session_state:
    st.session_state.principal_base = st.session_state.principal_df


# Streamlit's default date range only reaches 10 years ahead, too short for long loans
DATE_RANGE = {"min_value": date(2000, 1, 1), "max_value": date(2100, 12, 31)}


# 4. UI LAYOUT
st.title(":red[_Loan terms_]")

loan_inputs, loan_outputs = st.columns([1, 3])

with loan_inputs:
    st.header(":blue[Loan parameters]")

    # --- Inputs ---
    st.number_input("Loan provided", step=100000, format="%d", key="funding_amount")

    col_d1, col_d2 = st.columns(2)

    with col_d1:
        st.date_input("Funding date", key="funding_date", on_change=reset_schedules, **DATE_RANGE)
    with col_d2:
        st.date_input("Maturity date", key="maturity_date", on_change=reset_schedules, **DATE_RANGE)

    st.number_input(
        "Interest rate (%)",
        min_value=0.0, max_value=100.0, format="%.2f", step=0.1, key="interest_rate_pct"
    )
    st.session_state.interest_rate = st.session_state.interest_rate_pct / 100

    st.selectbox(
        "Interest repayment period",
        ("lump-sum", "annually", "semiannually", "quarterly", "monthly"),
        key="repayment_type",
        on_change=reset_schedules
    )

    # --- Data Editors ---
    st.write("Interest Schedule")
    st.session_state.interest_df = st.data_editor(
        st.session_state.interest_base,
        key="editor_interest",
        width='stretch',
        num_rows="dynamic"
    )

    st.write("Principal Schedule")
    st.session_state.principal_df = st.data_editor(
        st.session_state.principal_base,
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