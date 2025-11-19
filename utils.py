import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta

from typing import Optional

import numpy_financial as npf
from pyxirr import xirr

from openpyxl import load_workbook

pd.options.mode.chained_assignment = None

def end_of_month(date_input: date, no_of_months=0):
    new_date = date(date_input.year, date_input.month, 1)
    out = new_date + relativedelta(months=no_of_months + 1) - relativedelta(days=1)
    return out


def make_df_with_interest_rows(data_list, interest=True, blank_rows=0):
    # Create DF from list
    df = pd.DataFrame({"Date": data_list})

    # Add constant column
    if interest:
        df["Amount*"] = "interest"
    else:
        df["Amount*"] = "bullet"

    # Add blank rows if requested
    if blank_rows > 0:
        blank_df = pd.DataFrame({"Date": [None] * blank_rows, "Amount*": [None] * blank_rows})
        df = pd.concat([df, blank_df], ignore_index=True)

    return df


def get_period(interest_repayment_period:str) -> Optional[int]:
    if interest_repayment_period == "annually":
        ret = 12
    elif interest_repayment_period == "semiannually":
        ret = 6
    elif interest_repayment_period == "quarterly":
        ret = 3
    elif interest_repayment_period == "monthly":
        ret = 1
    else:
        ret = None

    return ret


def create_interest_payment_table(funding_date: date, maturity_date: date, payback_period: str) -> pd.DataFrame:

    interest_date = funding_date
    interests = []

    if payback_period != "lump-sum":
        no_of_months = get_period(payback_period)
        while end_of_month(interest_date, no_of_months) < maturity_date:
            interest_date = end_of_month(interest_date, no_of_months)
            interests.append(interest_date)

    interests.append(maturity_date)

    interests_df = make_df_with_interest_rows(interests, blank_rows=max(0, 12-len(interests)))
    return interests_df


def create_principal_payment_table(maturity_date: date):
    return make_df_with_interest_rows([maturity_date], interest=False ,blank_rows=11)


def get_repayment_table(principal, interest, interest_df, principal_df, maturity_date, funding_date):

    dates = []
    principal_left = principal
    principals_left = []
    interest_left = 0
    interests_left = []

    repayment_interest = []
    interests_due = []
    interests_paid = []

    principals_paid = []
    principals_repayment = []

    current_month = end_of_month(funding_date)

    while current_month <= end_of_month(maturity_date):

        if current_month == end_of_month(funding_date):
            principals_left.append(principal_left)
            interests_left.append(interest_left)

            repayment_interest.append(None)
            interests_due.append(None)
            interests_paid.append(None)

            principals_paid.append(None)
            principals_repayment.append(None)

        else:
            if len(dates) == 1:
                interest_due = principals_left[-1] * interest * (current_month.day + 1) / 360
            else:
                interest_due = principals_left[-1] * interest * current_month.day / 360
            interests_due.append(interest_due)

            if current_month in interest_df["Date"].to_list():
                interest_repayment = interest_df[interest_df["Date"] == current_month]["Amount*"].values[0]
                repayment_interest.append(interest_repayment)

                if interest_repayment == "interest":
                    interest_paid = interest_due + interests_left[-1]
                    interests_paid.append(interest_paid)
                    interests_left.append(0)

                else:
                    interest_paid = min((interest_due + interests_left[-1]), int(interest_repayment))
                    interests_paid.append(interest_paid)
                    interests_left.append(interest_due + interests_left[-1] - interests_paid[-1])

            else:
                repayment_interest.append("n/a")
                interests_left.append(interests_left[-1] + interest_due)
                interests_paid.append(0)

            if current_month in principal_df["Date"].to_list():
                principal_repayment = principal_df[principal_df["Date"] == current_month]["Amount*"].values[0]
                principals_repayment.append(principal_repayment)

                if principal_repayment == "bullet":
                    principals_paid.append(principals_left[-1])
                    principals_left.append(0)

                else:
                    principals_paid.append(min(int(principal_repayment), principals_left[-1]))
                    principals_left.append(principals_left[-1] - principals_paid[-1])
            else:
                principals_paid.append(0)
                principals_left.append(principals_left[-1])
                principals_repayment.append("n/a")
        dates.append(current_month)
        current_month = end_of_month(current_month, 1)

        gc_df = pd.DataFrame({
            "Month (calendar)": dates,
            "Repayment Interest": repayment_interest,
            "Repayment PV": principals_repayment,
            "Interest Due (net)": interests_due,
            "Interest Paid": interests_paid,
            "Interest Left": interests_left,
            "Principal Paid": principals_paid,
            "Principal Left":principals_left })

        gc_df["GC"] = gc_df["Interest Paid"] + gc_df["Principal Paid"]

    return gc_df


def create_cf_table(gc, wht, agent_fee, total_investment, Annual_Interest_Rate):
    Daily_Interest_Rate = (1 + Annual_Interest_Rate) ** (1 / 365) - 1

    cf = gc[["Month (calendar)", "Interest Paid", "Principal Paid"]]
    cf["WHT on Loan Interest"] = -wht * cf["Interest Paid"]
    cf["GC after costs after cap after cuts"] = cf["Interest Paid"] + cf["Principal Paid"] + cf["WHT on Loan Interest"]
    cf["Agent Fee"] = agent_fee * cf["GC after costs after cap after cuts"]
    cf["Net Cash flow before tax"] = cf["GC after costs after cap after cuts"] - cf["Agent Fee"]

    cf["Net Cash flow before tax"].iloc[0] = -total_investment

    # --- cumulative net cf ---

    Cumulative_Net_CF = []
    Net_multiple_for_Success_fee = []
    Cumulative_Net_CF_tech = 0

    for i, row in cf.iterrows():
        Cumulative_Net_CF_tech += row["Net Cash flow before tax"]
        Cumulative_Net_CF.append(Cumulative_Net_CF_tech)

        if i == 0:
            Net_multiple_for_Success_fee.append(None)
        else:
            Net_multiple_for_Success_fee.append(cf["Net Cash flow before tax"][1:(i + 1)].sum() / total_investment)

    cf["Cumulative Net CF"] = Cumulative_Net_CF
    cf["Net multiple for Success fee"] = Net_multiple_for_Success_fee

    # --- rest ---

    interest_due = []
    interest_due_tech = 0

    interest_paid = []
    interest_paid_tech = 0

    interest_left = []
    interest_left_tech = 0

    principal_paid = []
    principal_paid_tech = 0

    principal_left = []
    principal_left_tech = total_investment

    variable_interest = []
    variable_interest_tech = 0

    tax_base_cit = []
    tax_base_cit_tech = 0

    for i, row in cf.iterrows():
        if i == 0:
            interest_due.append(None)
            interest_paid.append(None)
            interest_left.append(interest_left_tech)
            principal_paid.append(None)
            principal_left.append(principal_left_tech)
            variable_interest.append(None)
            tax_base_cit.append(None)

        else:
            interest_due_tech = principal_left[i - 1] * ((1 + Daily_Interest_Rate) ** (
                (cf["Month (calendar)"][i] - cf["Month (calendar)"][i - 1]).days) - 1)
            interest_due.append(interest_due_tech)

            interest_paid_tech = max(min(row["Net Cash flow before tax"], interest_due_tech + interest_left[i - 1]), 0)
            interest_paid.append(interest_paid_tech)

            interest_left_tech = interest_left[i - 1] + interest_due_tech - interest_paid_tech
            interest_left.append(interest_left_tech)

            principal_paid_tech = min(row["Net Cash flow before tax"] - interest_paid_tech, principal_left[i - 1])
            principal_paid.append(principal_paid_tech)

            principal_left_tech = principal_left[i - 1] - principal_paid_tech
            principal_left.append(principal_left_tech)

            variable_interest_tech = row["Net Cash flow before tax"] - principal_paid_tech - interest_paid_tech
            variable_interest.append(variable_interest_tech)

    cf["Interest Due (net)"] = interest_due
    cf["Interest Paid - net"] = interest_paid
    cf["Interest Left"] = interest_left
    cf["Principal Paid - net"] = principal_paid
    cf["Principal Left"] = principal_left
    cf["Variable Interest"] = variable_interest

    return cf


def create_npv_table(cf, total_investment):
    npv_local_spv = cf[["Month (calendar)", "GC after costs after cap after cuts"]].rename(
        {"GC after costs after cap after cuts": "TECH for gross IRR"}, axis=1)

    npv_local_spv["TECH for gross IRR"].iloc[0] = -total_investment
    rate = xirr(npv_local_spv)

    Daily_IRR = (1 + rate) ** (1 / 365) - 1

    Principal_BoP = []
    Principal_BoP_tech = 0

    Interest = []
    Interest_tech = 0

    Amortization = []
    Amortization_tech = 0

    Principal_EoP_NPV = []
    Principal_EoP_NPV_tech = total_investment

    for i, row in npv_local_spv.iterrows():
        if i == 0:
            Principal_BoP.append(None)
            Interest.append(None)
            Amortization.append(None)
            Principal_EoP_NPV.append(Principal_EoP_NPV_tech)

        else:
            if abs(Principal_EoP_NPV[i - 1]) < 1:
                Principal_BoP_tech = 0
            else:
                Principal_BoP_tech = Principal_EoP_NPV[i - 1]

            Principal_BoP.append(Principal_BoP_tech)

            Interest_tech = Principal_BoP_tech * ((1 + Daily_IRR) ** (
                (npv_local_spv["Month (calendar)"][i] - npv_local_spv["Month (calendar)"][i - 1]).days) - 1)
            Interest.append(Interest_tech)

            Amortization_tech = row["TECH for gross IRR"] - Interest_tech
            Amortization.append(Amortization_tech)

            Principal_EoP_NPV_tech = Principal_BoP_tech - Amortization_tech
            Principal_EoP_NPV.append(Principal_EoP_NPV_tech)

    npv_local_spv["Principal BoP"] = Principal_BoP
    npv_local_spv["Interest"] = Interest
    npv_local_spv["Amortization"] = Amortization
    npv_local_spv["Principal EoP/NPV"] = Principal_EoP_NPV

    return npv_local_spv


def update_cf(cf, npv_local, total_investment, tax_rate, sicav_costs_monthly):
    cf["Tax base CIT"] = npv_local["Interest"] - cf["Agent Fee"] - cf["Interest Due (net)"]

    cf["Income tax (CIT)"] = cf["Tax base CIT"] * tax_rate
    cf["Net CF SICAV incoming"] = cf["Net Cash flow before tax"] - cf["Income tax (CIT)"]

    cf["Net CF SICAV incoming"][0] = -total_investment

    rate_sicav = xirr(cf[["Month (calendar)", "Net CF SICAV incoming"]])
    daily_rate_sicav = (1 + rate_sicav) ** (1 / 365) - 1

    sicav_npv = cf[["Month (calendar)", "Net CF SICAV incoming"]]

    principal_bob_sicav = []
    principal_bob_sicav_tech = 0

    interest_sicav = []
    interest_sicav_tech = 0

    amortization_sicav = []
    amortization_sicav_tech = 0

    principal_EoP_NPV_sicav = []
    principal_EoP_NPV_sicav_tech = 0

    for i, row in sicav_npv.iterrows():
        if i == 0:
            principal_bob_sicav.append(None)
            interest_sicav.append(None)
            amortization_sicav.append(None)
            principal_EoP_NPV_sicav.append(total_investment)

        else:
            if abs(principal_EoP_NPV_sicav[-1]) < 0:
                principal_bob_sicav_tech = 0
            else:
                principal_bob_sicav_tech = principal_EoP_NPV_sicav[-1]

            principal_bob_sicav.append(principal_bob_sicav_tech)
            interest_sicav_tech = principal_bob_sicav_tech * ((1 + daily_rate_sicav) ** (
                (sicav_npv["Month (calendar)"][i] - sicav_npv["Month (calendar)"][i - 1]).days) - 1)
            amortization_sicav_tech = row["Net CF SICAV incoming"] - interest_sicav_tech

            interest_sicav.append(interest_sicav_tech)
            amortization_sicav.append(amortization_sicav_tech)

            principal_EoP_NPV_sicav_tech = principal_bob_sicav_tech - amortization_sicav_tech
            principal_EoP_NPV_sicav.append(principal_EoP_NPV_sicav_tech)

    sicav_npv["Principal BoP"] = principal_bob_sicav
    sicav_npv["Interest"] = interest_sicav
    sicav_npv["Amortization"] = amortization_sicav
    sicav_npv["Principal EoP/NPV"] = principal_EoP_NPV_sicav

    cf["SICAV Costs"] = sicav_costs_monthly * sicav_npv["Principal BoP"]
    cf["Net CF after all taxes"] = cf["Net CF SICAV incoming"] - cf["SICAV Costs"]

    cf["Net CF after all taxes"][0] = -total_investment

    irr_sicav = []
    irr_sicav_tech = 0

    for i, row in cf.iterrows():
        try:
            irr_sicav_tech = xirr(cf[["Month (calendar)", "Net CF after all taxes"]][:(i + 1)])
            if irr_sicav_tech is None:
                irr_sicav_tech = -1
        except:
            irr_sicav_tech = -1

        irr_sicav.append(round(irr_sicav_tech, 4))

    cf["IRR"] = irr_sicav
    cf["Cumulative Net CF after all taxes"] = cf['Net CF after all taxes'].cumsum()
    cf["Net break even point // TEX"] = (cf["IRR"] > 0).astype(int)

    return cf, sicav_npv

def create_all_tables(gc, wht, agent_fee, total_investment, Annual_Interest_Rate, tax_rate, sicav_costs_monthly):
    cf = create_cf_table(gc=gc, wht=wht, agent_fee=agent_fee, total_investment=total_investment, Annual_Interest_Rate=Annual_Interest_Rate)
    npv_table = create_npv_table(cf, total_investment)
    cf, sicav_npv = update_cf(cf=cf, npv_local=npv_table, total_investment=total_investment, tax_rate=tax_rate, sicav_costs_monthly=sicav_costs_monthly)

    return cf, npv_table, sicav_npv

def save_model(input_file_name, **kwargs):
    wb = load_workbook(filename=f"{input_file_name}.xlsx")

    ws = wb["GC"]

    ws["D9"] = kwargs["funding_amount"]
    ws["D10"] = kwargs["funding_date"]
    ws["D11"] = kwargs["maturity_date"]
    ws["D12"] = kwargs["interest"]
    ws["D13"] = kwargs["repayment_period"]

    for i in range(12):
        ws[f"G{i + 7}"] = kwargs["interest_df"]["Date"].iloc[i]
        ws[f"H{i + 7}"] = kwargs["interest_df"]["Amount*"].iloc[i]

        ws[f"J{i + 7}"] = kwargs["principal_df"]["Date"].iloc[i]
        ws[f"K{i + 7}"] = kwargs["principal_df"]["Amount*"].iloc[i]

    ws = wb["Summary&CF_SICAV"]

    ws["E24"] = kwargs["wht_interest"]
    ws["E25"] = kwargs["agent_fee"]
    ws["E48"] = kwargs["SICAV_costs"]

    return wb

