import pandas as pd
import streamlit as st

import charts
from analysis import (deal_metrics, delay_payments, interest_at_maturity, principal_loss, shift_repayment,
                      timing_label)
from state import cached_model, keep_inputs, model_inputs, require_loan_terms
from utils import get_repayment_table

st.set_page_config(layout="wide", page_title="Sensitivity")
keep_inputs()

st.title(":red[_Sensitivity_]")
require_loan_terms()

s = st.session_state
inputs = model_inputs()
if inputs["total_investment"] <= 0:
    st.info("Please enter a Loan Amount to see the sensitivity.")
    st.stop()

gc = s.repayment_df


def xirr_of(schedule, **overrides):
    """After-tax XIRR for a repayment schedule; None when it cannot be calculated."""
    try:
        cf, _, _ = cached_model(schedule, **{**inputs, **overrides})
    except Exception:
        return None, None
    return deal_metrics(cf, inputs["total_investment"]), cf


base, _ = xirr_of(gc)
if base is None or base["xirr"] is None:
    st.error("The base case has no XIRR yet - check the loan terms and assumptions.")
    st.stop()

# ---------------------------------------------------------------- heatmap
st.header(":blue[XIRR vs. interest rate and repayment timing]")
st.caption("After-tax XIRR if the loan is repaid earlier or later than planned, at different interest rates. "
           "Interest keeps accruing at the loan rate until the actual repayment. "
           "Teal is better than the comparison XIRR, red is worse; the outlined cell is the current deal.")

c1, c2, c3, c4, c5 = st.columns(5)
rate_step = c1.number_input("Interest rate step (%-points)", min_value=0.05, value=0.5, step=0.25, format="%.2f")
month_step = c2.number_input("Timing step (months)", min_value=1, max_value=24, value=3, step=1)
max_early = c3.number_input("Up to months early", min_value=0, max_value=120, value=6, step=month_step)
max_late = c4.number_input("Up to months late", min_value=0, max_value=120, value=12, step=month_step)
reference = c5.number_input("Compare against XIRR (%)", value=round(base["xirr"] * 100, 2), step=0.5,
                            format="%.2f") / 100

base_rate = s.interest_rate_pct
rates = sorted({round(base_rate + rate_step * k, 4) for k in range(-3, 4) if base_rate + rate_step * k >= 0})

# Early repayment can go back no further than the month after funding
months_to_maturity = ((s.maturity_date.year - s.funding_date.year) * 12
                      + s.maturity_date.month - s.funding_date.month)
shifts = sorted({0, *range(-month_step, -max_early - 1, -month_step), *range(month_step, max_late + 1, month_step)})
shifts = [m for m in shifts if m > -months_to_maturity]


@st.cache_data(show_spinner=False)
def timing_grid(rates, base_rate, shifts, funding_amount, interest_df, principal_df, funding_date, maturity_date, inputs):
    rows = []
    for months in shifts:
        interest, principal, maturity = shift_repayment(interest_df, principal_df, funding_date, maturity_date, months)
        for rate in rates:
            schedule = get_repayment_table(funding_amount, rate / 100, interest, principal, maturity, funding_date)
            try:
                cf, _, _ = cached_model(schedule, **inputs)
                xirr = deal_metrics(cf, inputs["total_investment"])["xirr"]
            except Exception:
                xirr = None
            rows.append({"X": f"{rate:.2f}%", "Y": timing_label(months), "XIRR": xirr,
                         "Base": abs(rate - base_rate) < 1e-9 and months == 0})
    grid = pd.DataFrame(rows)
    grid["XIRR"] = grid["XIRR"].astype(float)
    return grid


with st.spinner("Calculating..."):
    grid = timing_grid(rates, base_rate, shifts, s.funding_amount, s.interest_df, s.principal_df,
                       s.funding_date, s.maturity_date, inputs)

x_order = [f"{r:.2f}%" for r in rates]
y_order = [timing_label(m) for m in shifts]  # early at the top, late at the bottom
st.altair_chart(
    charts.xirr_heatmap(grid, "Loan interest rate", "Repayment vs. plan", reference, x_order=x_order, y_order=y_order),
    width="stretch",
)
with st.expander("Table"):
    table = grid.pivot(index="Y", columns="X", values="XIRR").loc[y_order, x_order]
    st.dataframe(table.map(lambda v: "n/a" if pd.isna(v) else f"{v:.2%}"))

# ---------------------------------------------------------------- stress scenarios
st.header(":blue[Stress scenarios]")
st.caption("What happens to the return if the borrower pays late, pays interest only at the end, "
           "or does not repay all principal. Late payments carry no extra interest.")

c1, c2, _ = st.columns([1, 1, 2])
delay = c1.number_input("Payment delay (months)", min_value=1, max_value=60, value=6, step=1)
loss = c2.number_input("Principal loss (%)", min_value=0.0, max_value=100.0, value=20.0, step=5.0, format="%.1f") / 100

scenarios = {
    "Base case": gc,
    f"All payments {delay} months late": delay_payments(gc, delay),
    "Interest paid only at maturity": interest_at_maturity(gc),
    f"{loss:.0%} principal loss": principal_loss(gc, loss),
    f"{delay} months late and {loss:.0%} loss": principal_loss(delay_payments(gc, delay), loss),
}

results = []
for name, schedule in scenarios.items():
    metrics, _ = xirr_of(schedule)
    if metrics is None:
        metrics = {"xirr": None, "net_multiple": None, "net_gain": None, "payback_month": None}
    results.append({
        "Scenario": name,
        "XIRR": metrics["xirr"],
        "vs base": None if metrics["xirr"] is None else metrics["xirr"] - base["xirr"],
        "Net multiple": metrics["net_multiple"],
        "Net gain": metrics["net_gain"],
        "Payback (month)": metrics["payback_month"],
    })
results = pd.DataFrame(results)
results["XIRR"] = results["XIRR"].astype(float)

st.altair_chart(charts.scenario_bars(results), width="stretch")
st.dataframe(
    results.assign(**{
        "Net gain": results["Net gain"].round(0),
        "Payback (month)": results["Payback (month)"].map(lambda v: "not reached" if pd.isna(v) else str(int(v))),
    }),
    hide_index=True,
    width="stretch",
    column_config={
        "XIRR": st.column_config.NumberColumn(format="percent"),
        "vs base": st.column_config.NumberColumn(format="percent"),
        "Net multiple": st.column_config.NumberColumn(format="%.2fx"),
        "Net gain": st.column_config.NumberColumn(format="localized"),
    },
)
