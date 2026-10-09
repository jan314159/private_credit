import io
from datetime import date

import pandas as pd
import streamlit as st

from utils import create_all_tables, save_model
from state import keep_inputs

# 1. SETUP
st.set_page_config(layout="wide", page_title="Assumptions & Outcome")

# Keeps every input (on this and the other pages) when switching pages
keep_inputs()

# 2. SAFETY CHECK
# This page relies on the calculation from the previous step (Loan Terms).

if "repayment_df" not in st.session_state or st.session_state.repayment_df.empty:
    st.warning("⚠️ Please configure the 'Loan Terms' first to generate the base schedule.")
    st.stop()

# 3. LAYOUT & INPUTS
inputs_outcome_col, col_1, col_2 = st.columns([1, 1, 1])


with inputs_outcome_col:
    st.header(":blue[Main assumptions]")

    # streamlined inputs using session_state keys directly
    # We keep the inputs as percentages (0-100) for UI, divide by 100 for logic.

    st.text_input("Project name", key="project_name")

    wht = st.number_input("WHT (%)", step=0.5, format="%.2f", key="wht_input") / 100

    agent_fee_input = st.number_input("Agent fee (%)", step=0.5, format="%.2f", key="in_agent_fee")
    agent_fee = agent_fee_input / 100

    # SICAV: Input is Annual %, Logic requires Monthly %
    sicav_input = st.number_input("Sicav costs p.a. (%)", step=0.25, format="%.2f", key="in_sicav")
    sicav_costs_monthly = (sicav_input / 100) / 12

    # annual_rate_input = st.number_input("Annual interest rate (%)", step=0.5, value=5.0, format="%.2f",
    #                                     key="in_annual_rate")
    # annual_interest_rate = annual_rate_input / 100
    #
    # tax_rate_input = st.number_input("Tax rate (%)", step=0.25, value=25.0, format="%.2f", key="in_tax_rate")
    # tax_rate = tax_rate_input / 100

    other_costs = st.number_input("Other Costs", step=1000, format="%d", key="in_other_costs")

    # Loan provided comes from previous step, but we allow override or view here
    # Using a separate key to avoid conflict if you go back to the first script
    funding_amount = st.number_input("Loan provided", value=st.session_state.get("funding_amount", 0), step=100000,
                                     format="%d", disabled=True)

    total_investment = other_costs + funding_amount
    st.metric("Total Investment", f"{total_investment:,.0f}")

# 4. CORE CALCULATION
# Only run if we have valid investment data
try:
    cf, npv_table, sicav_npv = create_all_tables(
        gc=st.session_state.repayment_df,
        wht=wht,
        agent_fee=agent_fee,
        total_investment=total_investment,
        Annual_Interest_Rate=0,
        tax_rate=0,
        sicav_costs_monthly=sicav_costs_monthly
    )
except Exception as e:
    st.error(f"Calculation Error: {e}")
    st.stop()

# 5. OUTCOME DATAFRAME GENERATION
if not cf.empty and cf.shape[0] > 1:
    # Helper variables for readability
    costs_cols = ['Agent Fee', 'Income tax (CIT)', 'SICAV Costs']
    income_cols = ["Interest Paid", "Principal Paid", "WHT on Loan Interest"]

    total_income = cf[income_cols].sum().sum()
    total_costs = cf[costs_cols].sum().sum()
    net_profit = total_income - total_costs
    gc_weighted = cf['GC after costs after cap after cuts']

    # Logic for Break Even
    break_even_list = cf['Net break even point // TEX'].to_list()
    break_even_idx = break_even_list.index(1) if 1 in break_even_list else "N/A"

    # Dictionary is cleaner than list of strings
    outcome_data = {
        "XIRR (after tax)": f"{cf['IRR'].iloc[-1]:.2%}",
        "Net Break Even (months)": f"{break_even_idx}",
        "Net Multiple (after tax)": f"{cf['Cumulative Net CF after all taxes'].iloc[-1] / total_investment + 1:.2f}x",
        "Net Profit (after tax)": f"{net_profit:,.0f}",
        "GC Total": f"{total_income:,.0f}",
        "Gross Multiple": f"{total_income / total_investment:,.2f}x",
        "Weighted Avg Life": f"{(gc_weighted * cf.index).sum() / gc_weighted.sum():.1f}",
        "Recovery Rate": f"{total_income / funding_amount:.2%}",
        "Interest Paid": f"{cf['Interest Paid'].sum():,.0f}",
        "Principal Paid": f"{cf['Principal Paid'].sum():,.0f}",
        "WHT on Loan Interest": f"{cf['WHT on Loan Interest'].sum():,.0f}"
    }

    model_outcome = pd.DataFrame.from_dict(outcome_data, orient='index', columns=["Investment overview"])


# 6. DISPLAY TABLES
st.header(":blue[Cash flow]")
st.dataframe(
    cf,
    width='stretch',
column_config={
        "Interest Paid": st.column_config.NumberColumn(format="localized", step=1),
        "Principal Paid": st.column_config.NumberColumn(format="localized", step=1),
        "WHT on Loan Interest": st.column_config.NumberColumn(format="localized", step=1),
        "GC after costs after cap after cuts": st.column_config.NumberColumn(format="localized", step=1),
        "Agent Fee": st.column_config.NumberColumn(format="localized", step=1),
        "Net Cash flow before tax": st.column_config.NumberColumn(format="localized", step=1),
        "Cumulative Net CF": st.column_config.NumberColumn(format="localized", step=1),
        "Net multiple for Success fee": st.column_config.NumberColumn(format="%.2f"),
        "Interest Due (net)": st.column_config.NumberColumn(format="localized", step=1),
        "Interest Paid - net": st.column_config.NumberColumn(format="localized", step=1),
        "Interest Left": st.column_config.NumberColumn(format="localized", step=1),
        "Principal Paid - net": st.column_config.NumberColumn(format="localized", step=1),
        "Principal Left": st.column_config.NumberColumn(format="localized", step=1),
        "Variable Interest": st.column_config.NumberColumn(format="localized", step=1),
        "Tax base CIT": st.column_config.NumberColumn(format="localized", step=1),
        "Income tax (CIT)": st.column_config.NumberColumn(format="localized", step=1),
        "Net CF SICAV incoming": st.column_config.NumberColumn(format="localized", step=1),
        "SICAV Costs": st.column_config.NumberColumn(format="localized", step=1),
        "Net CF after all taxes": st.column_config.NumberColumn(format="localized", step=1),
        "IRR": st.column_config.NumberColumn(format="percent"),
        "Cumulative Net CF after all taxes": st.column_config.NumberColumn(format="localized", step=1),
        "Net break even point // TEX": st.column_config.NumberColumn(format="%.2f"),
    }
)

currency_fmt = st.column_config.NumberColumn(format="$%d")
npv_col, sicav_col = st.columns(2)
npv_col.subheader(":blue[NPV - Local SPV]")
npv_col.dataframe(
    npv_table,
    hide_index=True,
    width='stretch',
    column_config={
        "TECH for gross IRR": st.column_config.NumberColumn(format="localized", step=1),
        "Principal BoP": st.column_config.NumberColumn(format="localized", step=1),
        "Interest": st.column_config.NumberColumn(format="localized", step=1),
        "Amortization": st.column_config.NumberColumn(format="localized", step=1),
        "Principal EoP/NPV": st.column_config.NumberColumn(format="localized", step=1)
    }
)

sicav_col.subheader(":blue[NPV - SICAV]")
sicav_col.dataframe(
    sicav_npv,
    hide_index=True,
    width='stretch',
    column_config={
        "Net CF SICAV incoming": st.column_config.NumberColumn(format="localized", step=1),
        "Principal BoP": st.column_config.NumberColumn(format="localized", step=1),
        "Interest": st.column_config.NumberColumn(format="localized", step=1),
        "Amortization": st.column_config.NumberColumn(format="localized", step=1),
        "Principal EoP/NPV": st.column_config.NumberColumn(format="localized", step=1)
    }
)

with col_1:
    st.header(":blue[APS fees]")
    engagement_fee = st.number_input("Engagement fee", step=1000, format="%d", key="eng_fee")
    arrangement_fee = st.number_input("Arrangement Fee", step=1000, format="%d", key="arr_fee")

    if not cf.empty:
        funding_year = st.session_state.funding_date.year
        # Boolean mask for year filtering
        mask_year = cf['Month (calendar)'].apply(lambda x: x.year) == funding_year

        agent_fee_sum = cf['Agent Fee'].sum()
        agent_fee_year = cf.loc[mask_year, 'Agent Fee'].sum()

        aps_data = {
            "Metric": [
                "Current year",
                "APS fees total",
                "New AMF total",
                f"New AMF {funding_year}",
                "APSI fees total",
                f"APSI fees {funding_year}"
            ],
            "Value": [
                str(funding_year),
                f"{agent_fee_sum + arrangement_fee + engagement_fee:,.0f}",
                f"{agent_fee_sum:,.0f}",
                f"{agent_fee_year:,.0f}",
                f"{arrangement_fee + engagement_fee:,.0f}",
                f"{arrangement_fee + engagement_fee:,.0f}"
            ]
        }
        st.dataframe(pd.DataFrame(aps_data), hide_index=True, width='stretch')

with col_2:
    st.header(":blue[Model outcome]")

    st.dataframe(model_outcome, width='stretch')




# 7. EXCEL GENERATION (Cached & Optimized)
# We wrap the file generation in a function cached by Streamlit.
# This prevents the app from regenerating the Excel file on every tiny click,
# which is usually the slowest part of these apps.

@st.cache_data(show_spinner=False)
def convert_df_to_excel(f_amt, f_date, m_date, rate, rep_period, int_df, prin_df, wht, agent, sicav,
                        project_name, eng_fee, arr_fee):
    # Calls your original utils function
    wb = save_model(
        "private_credit_template",
        funding_amount=f_amt,
        funding_date=f_date,
        maturity_date=m_date,
        interest=rate,
        repayment_period=rep_period,
        interest_df=int_df,
        principal_df=prin_df,
        wht_interest=wht,
        agent_fee=agent,
        SICAV_costs=sicav,
        project_name=project_name,
        engagement_fee=eng_fee,
        arrangement_fee=arr_fee
    )
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# Only generate the download button if data exists
if "funding_amount" in st.session_state:
    excel_data = convert_df_to_excel(
        st.session_state.funding_amount,
        st.session_state.funding_date,
        st.session_state.maturity_date,
        st.session_state.get("interest_rate", 0),  # Handle potential missing key safety
        st.session_state.get("repayment_type", "lump-sum"),
        st.session_state.interest_df,
        st.session_state.principal_df,
        wht,
        agent_fee,
        sicav_costs_monthly,  # Note: passing the calculated monthly cost
        st.session_state.project_name,
        engagement_fee,
        arrangement_fee
    )

    st.sidebar.download_button(
        label="⬇️ Download Model",
        data=excel_data,
        file_name=f"{st.session_state.project_name}_{str(date.today()).replace('-', '')}.xlsx",
        mime="application/vnd.ms-excel"
    )