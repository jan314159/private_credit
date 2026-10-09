import pandas as pd
import streamlit as st

import charts
from analysis import deal_metrics, delay_payments, interest_at_maturity, principal_loss
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
st.header(":blue[XIRR sensitivity]")
st.caption("After-tax XIRR when the loan interest rate and one other assumption change. "
           "Blue is better than the comparison XIRR, red is worse; the outlined cell is the current deal.")

# Second axis: label -> (session key holding the % input, model input it drives, default step in %-points)
DRIVERS = {
    "WHT (%)": ("wht_input", "wht", 2.5),
    "Agent fee (%)": ("in_agent_fee", "agent_fee", 0.25),
    "SICAV costs p.a. (%)": ("in_sicav", "sicav_costs_monthly", 0.5),
}

c1, c2, c3, c4 = st.columns(4)
driver = c1.selectbox("Compare interest rate with", list(DRIVERS))
key, model_key, default_step = DRIVERS[driver]
rate_step = c2.number_input("Interest rate step (%-points)", min_value=0.05, value=0.5, step=0.25, format="%.2f")
driver_step = c3.number_input(f"{driver.split(' (')[0]} step (%-points)", min_value=0.05, value=default_step,
                              step=0.25, format="%.2f", key=f"step_{key}")
reference = c4.number_input("Compare against XIRR (%)", value=round(base["xirr"] * 100, 2), step=0.5,
                            format="%.2f") / 100


def to_model(value_pct):
    return value_pct / 100 / 12 if model_key == "sicav_costs_monthly" else value_pct / 100


base_rate = s.interest_rate_pct
base_driver = s[key]
rates = sorted({round(base_rate + rate_step * k, 4) for k in range(-3, 4) if base_rate + rate_step * k >= 0})
drivers = sorted({round(base_driver + driver_step * k, 4) for k in range(-2, 3) if base_driver + driver_step * k >= 0})

rows = []
with st.spinner("Calculating..."):
    for rate in rates:
        schedule = get_repayment_table(s.funding_amount, rate / 100, s.interest_df, s.principal_df,
                                       s.maturity_date, s.funding_date)
        for value in drivers:
            metrics, _ = xirr_of(schedule, **{model_key: to_model(value)})
            rows.append({
                "X": f"{rate:.2f}%", "Y": f"{value:.2f}%",
                "XIRR": None if metrics is None else metrics["xirr"],
                "Base": abs(rate - base_rate) < 1e-9 and abs(value - base_driver) < 1e-9,
            })
grid = pd.DataFrame(rows)
grid["XIRR"] = grid["XIRR"].astype(float)

st.altair_chart(
    charts.xirr_heatmap(grid, "Loan interest rate", driver, reference,
                        x_order=[f"{r:.2f}%" for r in rates], y_order=[f"{v:.2f}%" for v in reversed(drivers)]),
    width="stretch",
)
with st.expander("Table"):
    table = grid.pivot(index="Y", columns="X", values="XIRR")
    table = table.loc[[f"{v:.2f}%" for v in reversed(drivers)], [f"{r:.2f}%" for r in rates]]
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
