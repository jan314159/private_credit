import pandas as pd
import streamlit as st
from utils import *

import io

pd.options.mode.chained_assignment = None


st.set_page_config(layout="wide")

inputs_outcome_col, col_1, col_2 = st.columns([3, 2, 4])  # 1:3 ratio

with inputs_outcome_col:
    st.header(":blue[Main assumptions]")
    if "wht" not in st.session_state:
        st.session_state.wht = st.number_input("wht (in %)", step=0.5, format="%f", value=0.0) / 100
    else:
        st.session_state.wht = st.number_input("wht (in %)", step=0.5, format="%f",value=st.session_state.wht*100) / 100

    if "agent_fee" not in st.session_state:
        st.session_state.agent_fee = st.number_input("Agent fee (in %)", step=0.5, format="%f", value=0.0) / 100
    else:
        st.session_state.agent_fee = st.number_input("Agent fee (in %)", step=0.5, format="%f",value=st.session_state.agent_fee*100) / 100

    if "sicav_costs" not in st.session_state:
        st.session_state.sicav_costs = st.number_input("Sicav costs p.a. (in %)", step=0.25, format="%f", value=3.0) / 100 / 12
    else:
        st.session_state.sicav_costs = st.number_input("Sicav costs p.a. (in %)", step=0.5, format="%f",value=st.session_state.sicav_costs*100*12) / 100 / 12

    if "annual_interest_rate" not in st.session_state:
        st.session_state.annual_interest_rate = st.number_input("Annual interest rate (in %)", step=0.5, format="%f", value=5.0) / 100
    else:
        st.session_state.annual_interest_rate = st.number_input("Annual interest rate (in %)", step=0.5, format="%f",value=st.session_state.annual_interest_rate*100) / 100

    if "tax_rate" not in st.session_state:
        st.session_state.tax_rate = st.number_input("Tax rate (in %)", step=0.25, format="%f", value=0.25) / 100
    else:
        st.session_state.tax_rate = st.number_input("Tax rate (in %)", step=0.5, format="%f",value=st.session_state.tax_rate*100) / 100

    if "other_costs" not in st.session_state:
        st.session_state.other_costs = st.number_input("Other Costs", step=1, format="%d", value=0)
    else:
        st.session_state.other_costs = st.number_input("Other Costs", step=100000, format="%d", value=st.session_state.other_costs)

    if "funding_amount" not in st.session_state:
        st.session_state.funding_amount = st.number_input("Loan provided", step=100000,format="%d", value=0)
    else:
        st.session_state.funding_amount = st.number_input("Loan provided", step=100000, format="%d", value=st.session_state.funding_amount)

    total_investment = st.session_state.other_costs + st.session_state.funding_amount

    st.metric("Total Investment", f"{total_investment:,.0f}")

    st.subheader("Model Outcome", divider="blue")

try:
    cf, npv_table, sicav_npv = create_all_tables(
        gc=st.session_state.repayment_df,
        wht=st.session_state.wht,
        agent_fee=st.session_state.agent_fee,
        total_investment=total_investment,
        Annual_Interest_Rate=st.session_state.annual_interest_rate,
        tax_rate=st.session_state.tax_rate,
        sicav_costs_monthly=st.session_state.sicav_costs)

    st.session_state.cf = cf
    st.session_state.npv_table = npv_table
    st.session_state.sicav_npv = sicav_npv

except AttributeError:
    st.session_state.cf = pd.DataFrame()
    st.session_state.npv_table = pd.DataFrame()
    st.session_state.sicav_npv = pd.DataFrame()

costs_cols = ['Agent Fee', 'Income tax (CIT)', 'SICAV Costs']
income_cols = ["Interest Paid", "Principal Paid", "WHT on Loan Interest"]

if st.session_state.cf.shape[0] > 1:
    model_outcome = pd.DataFrame(
    [f"{cf['IRR'].iloc[-1]:.2%}",
     f"{cf['Net break even point // TEX'].to_list().index(1)} months",
     f"{cf['Cumulative Net CF after all taxes'].iloc[-1]/total_investment + 1:.2f}",
     f"{cf[income_cols].sum().sum() - cf[costs_cols].sum().sum():,.0f}",
     f"{cf[income_cols].sum().sum():,.0f}",
     f"{cf[income_cols].sum().sum() / total_investment:,.2f}",
     f"{(cf['GC after costs after cap after cuts'] * cf.index).sum() / cf['GC after costs after cap after cuts'].sum():.1f}",
     f"{cf[income_cols].sum().sum()/st.session_state.funding_amount:.2%}",
     f"{cf['Interest Paid'].sum():,.0f}",
     f"{cf['Principal Paid'].sum():,.0f}",
     f"{cf['WHT on Loan Interest'].sum():,.0f}"],
    index=["XIRR (after tax)",
           "Net Break Event Point (after tax)",
           "Net Multiple (after tax)",
           "Net Profit (after tax)",
           "GC Total",
           "Gross Multiple",
           "Weighted Average Life",
           "Recovery Rate",
           "Interest Paid",
           "Principal Paid",
           "WHT on Loan Interest"],
    columns=["Investment overview"])

else:
    model_outcome = pd.DataFrame()

with inputs_outcome_col:
    st.dataframe(model_outcome)

with st.container():
    st.header(":blue[Cash flow]")
    st.dataframe(st.session_state.cf)


with col_1:
    st.header(":blue[APS fees]")
    if "engagement_fee" not in st.session_state:
        st.session_state.engagement_fee = st.number_input("Engagement fee", step=1000, format="%d", value=0)
    else:
        st.session_state.engagement_fee = st.number_input("Engagement fee", step=1000, format="%d", value=st.session_state.engagement_fee)

    if "arrangement_fee" not in st.session_state:
        st.session_state.arrangement_fee = st.number_input("Arrangement Fee", step=1000, format="%d", value=0)
    else:
        st.session_state.arrangement_fee = st.number_input("Arrangement Fee", step=1000, format="%d", value=st.session_state.arrangement_fee)

    aps_fees = pd.DataFrame(
        [["Current year", st.session_state.funding_date.year],
         ["APS fees total", f"{st.session_state.cf['Agent Fee'].sum() + st.session_state.arrangement_fee + st.session_state.engagement_fee:,.0f}"],
         ["New AMF total", f"{st.session_state.cf['Agent Fee'].sum():,.0f}"],
         [f"New AMF {st.session_state.funding_date.year}", f"{st.session_state.cf[st.session_state.cf['Month (calendar)'].apply(lambda x: x.year) == st.session_state.funding_date.year]['Agent Fee'].sum():,.0f}"],
         ["APSI fees total", f"{st.session_state.arrangement_fee + st.session_state.engagement_fee:,.0f}"],
         [f"APSI fees {st.session_state.funding_date.year}", f"{st.session_state.arrangement_fee + st.session_state.engagement_fee:,.0f}"]],
        columns=["APS Fees", "Total"])
    st.dataframe(aps_fees, hide_index=True)


with col_2:
    st.header(":blue[NPVs]")

    st.subheader("NPV - Local SPV")
    st.dataframe(
        st.session_state.npv_table,
        hide_index=True,
        column_config={
            "TECH for gross IRR": st.column_config.NumberColumn(format="localized", step=1),
            "Principal BoP": st.column_config.NumberColumn(format="localized", step=1),
            "Interest": st.column_config.NumberColumn(format="localized", step=1),
            "Amortization": st.column_config.NumberColumn(format="localized", step=1),
            "Principal EoP/NPV": st.column_config.NumberColumn(format="localized", step=1)
        })

    st.subheader("NPV - SICAV")
    st.dataframe(st.session_state.sicav_npv, column_config={
            "Net CF SICAV incoming": st.column_config.NumberColumn(format="localized", step=1),
            "Principal BoP": st.column_config.NumberColumn(format="localized", step=1),
            "Interest": st.column_config.NumberColumn(format="localized", step=1),
            "Amortization": st.column_config.NumberColumn(format="localized", step=1),
            "Principal EoP/NPV": st.column_config.NumberColumn(format="localized", step=1)
        })

workbook = save_model(
    "private_credit_template",
    funding_amount=st.session_state.funding_amount,
    funding_date=st.session_state.funding_date,
    maturity_date=st.session_state.maturity_date,
    interest=st.session_state.interest_rate,
    repayment_period=st.session_state.interest_repayment,
    interest_df=st.session_state.interest_df,
    principal_df=st.session_state.principal_df,
    wht_interest=st.session_state.wht,
    agent_fee=st.session_state.agent_fee,
    SICAV_costs=st.session_state.sicav_costs)
excel_buffer = io.BytesIO()
workbook.save(excel_buffer)

st.sidebar.download_button(
    label="⬇️ Download Model",
    data=excel_buffer.getvalue(),
    file_name="streamlit_openpyxl_output.xlsx",
    mime="application/vnd.ms-excel")