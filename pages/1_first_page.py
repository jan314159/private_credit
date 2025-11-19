import os
import locale

import streamlit as st
import pandas as pd
from datetime import date
import io
from utils import *

locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

def style_blue():
    return f'background-color: #005864; color: white'


def style_orange_text():
    return f'color: #E83E33'


st.set_page_config(layout="wide")
st.title(":red[_Loan terms_]")


loan_inputs, loan_outputs = st.columns([1, 3])  # 1:3 ratio

with loan_inputs:
    st.header(":blue[Loan parameters]")
    if "funding_amount" not in st.session_state:
        st.session_state.funding_amount = st.number_input("Loan provided", step=100000,format="%d", value=0)
    else:
        st.session_state.funding_amount = st.number_input("Loan provided", step=100000, format="%d", value=st.session_state.funding_amount)

    if "funding_date" not in st.session_state:
        st.session_state.funding_date = st.date_input("Funding date", value="today")
    else:
        st.session_state.funding_date = st.date_input("Funding date", value=st.session_state.funding_date)

    if "maturity_date" not in st.session_state:
        st.session_state.maturity_date = st.date_input("Maturity date", value="today")
    else:
        st.session_state.maturity_date = st.date_input("Maturity date", value=st.session_state.maturity_date)

    if "interest_rate" not in st.session_state:
        st.session_state.interest_rate = st.number_input("Interest rate (%)", min_value=0.0, max_value=100.0, value="min", format="%.2f", step=0.1) / 100
    else:
        st.session_state.interest_rate = st.number_input("Interest rate (%)", min_value=0.0, max_value=100.0, value=st.session_state.interest_rate*100, format="%.2f", step=0.1) / 100

    interest_repayment_list = ("lump-sum", "annually", "semiannually", "quarterly", "monthly")
    if "interest_repayment" not in st.session_state:
        st.session_state.interest_repayment = st.selectbox("Interest repayment period", interest_repayment_list)
    else:
        st.session_state.interest_repayment = st.selectbox("Interest repayment period", interest_repayment_list, index=interest_repayment_list.index(st.session_state.interest_repayment))

    initial_interest_df = create_interest_payment_table(st.session_state.funding_date, st.session_state.maturity_date, st.session_state.interest_repayment)
    initial_principal_df = create_principal_payment_table(st.session_state.maturity_date)

    st.write("Interst")
    st.session_state.interest_df = st.data_editor(initial_interest_df, key="interest_inputs")

    st.write("Principal")
    st.session_state.principal_df = st.data_editor(initial_principal_df, key="principal_inputs")

formatter = {
    'Value': '{:,.0f}'
}

with loan_outputs:
    st.header(":blue[Cash flow]")


    try:
        st.session_state.repayment_df = get_repayment_table(
            principal=st.session_state.funding_amount,
            interest=st.session_state.interest_rate,
            interest_df=st.session_state.interest_df,
            principal_df=st.session_state.principal_df,
            maturity_date=st.session_state.maturity_date,
            funding_date=st.session_state.funding_date)

    except TypeError:
        st.session_state.repayment_df = get_repayment_table(
            principal=st.session_state.funding_amount,
            interest=st.session_state.interest_rate,
            interest_df=initial_interest_df,
            principal_df=initial_principal_df,
            maturity_date=st.session_state.maturity_date,
            funding_date=st.session_state.funding_date)


    st.dataframe(
        st.session_state.repayment_df,
        column_config={
            "Interest Due (net)": st.column_config.NumberColumn(format="localized", step=1),
            "Interest Paid": st.column_config.NumberColumn(format="localized", step=1),
            "Interest Left": st.column_config.NumberColumn(format="localized", step=1),
            "Principal Paid": st.column_config.NumberColumn(format="localized", step=1),
            "Principal Left": st.column_config.NumberColumn(format="localized", step=1),
            "GC": st.column_config.NumberColumn(format="localized", step=1)
        })


interest_due_col = "Interest Due (net)"
interest_paid_col = "Interest Paid"
principal_paid_col = "Principal Paid"
gc_col = "GC"

if st.session_state.repayment_df.shape[0] > 1:
    st.sidebar.metric("Interest due", f"{st.session_state.repayment_df[interest_due_col].sum():,.0f}",
                      chart_data=st.session_state.repayment_df[interest_due_col][1:], chart_type="area", border=True)
    st.sidebar.metric("Interest Paid", f"{st.session_state.repayment_df[interest_paid_col].sum():,.0f}", border=True)
    st.sidebar.metric("Principal Paid", f"{st.session_state.repayment_df[principal_paid_col].sum():,.0f}", border=True)
    st.sidebar.metric("GC", f"{st.session_state.repayment_df[gc_col].sum():,.0f}" , border=True)

