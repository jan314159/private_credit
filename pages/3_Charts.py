import streamlit as st

import charts
from analysis import deal_metrics, fees_by_year, waterfall_steps
from state import cached_model, keep_inputs, model_inputs, require_loan_terms

st.set_page_config(layout="wide", page_title="Charts")
keep_inputs()

st.title(":red[_Charts_]")
require_loan_terms()

inputs = model_inputs()
total_investment = inputs["total_investment"]
if total_investment <= 0:
    st.info("Please enter a Loan Amount to see the charts.")
    st.stop()

gc = st.session_state.repayment_df
try:
    cf, _, _ = cached_model(gc, **inputs)
except Exception as e:
    st.error(f"Calculation Error: {e}")
    st.stop()

m = deal_metrics(cf, total_investment)

# --- Headline figures ---
k1, k2, k3, k4 = st.columns(4)
k1.metric("XIRR (after tax)", "n/a" if m["xirr"] is None else f"{m['xirr']:.2%}", border=True)
k2.metric("Net multiple (after tax)", f"{m['net_multiple']:.2f}x", border=True)
k3.metric("Net gain (after all costs)", f"{m['net_gain']:,.0f}", border=True)
k4.metric("Payback", "not reached" if m["payback_month"] is None else f"month {m['payback_month']}", border=True)

# --- Charts ---
left, right = st.columns(2)

with left:
    st.subheader(":blue[Cumulative net cash flow]")
    st.caption("After WHT, agent fee and SICAV costs. The line crosses zero at payback.")
    st.altair_chart(charts.cumulative_cf(cf, m["payback_month"]), width="stretch")

with right:
    st.subheader(":blue[From collections to net gain]")
    st.caption("Where the money goes: everything collected, minus costs and the investment.")
    steps = waterfall_steps(cf, total_investment)
    st.altair_chart(charts.waterfall(steps), width="stretch")

left, right = st.columns(2)

with left:
    st.subheader(":blue[Outstanding balance]")
    st.caption("Principal still owed, with interest accrued but not yet paid on top.")
    st.altair_chart(charts.outstanding_balance(gc), width="stretch")

with right:
    st.subheader(":blue[Interest by month]")
    st.caption("Interest expected each payment month, before WHT and costs.")
    st.altair_chart(charts.interest_by_month(gc), width="stretch")

left, right = st.columns(2)

with left:
    st.subheader(":blue[Fees by year]")
    st.caption("Agent fee per year; engagement and arrangement fees in the funding year.")
    fees = fees_by_year(cf, st.session_state.funding_date.year,
                        st.session_state.eng_fee + st.session_state.arr_fee)
    st.altair_chart(charts.fees_by_year(fees), width="stretch")

with st.expander("Chart data"):
    st.dataframe(steps[["Step", "Amount"]], hide_index=True,
                 column_config={"Amount": st.column_config.NumberColumn(format="localized")})
    st.dataframe(fees, hide_index=True,
                 column_config={c: st.column_config.NumberColumn(format="localized") for c in ["Agent fee", "Upfront fees"]})
