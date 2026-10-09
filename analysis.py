"""Deal metrics and what-if scenarios built on the cash-flow model in utils.py (no Streamlit here)."""
import numpy as np
import pandas as pd

from utils import create_all_tables, end_of_month

# Fixed on the Summary page by design
TAX_RATE = 0
ANNUAL_INTEREST_RATE = 0


def run_model(gc, wht, agent_fee, total_investment, sicav_costs_monthly):
    return create_all_tables(
        gc=gc,
        wht=wht,
        agent_fee=agent_fee,
        total_investment=total_investment,
        Annual_Interest_Rate=ANNUAL_INTEREST_RATE,
        tax_rate=TAX_RATE,
        sicav_costs_monthly=sicav_costs_monthly,
    )


def deal_metrics(cf, total_investment):
    """Headline figures, defined as on the Summary page.

    xirr is None while it is undefined; payback_month is the first month with a positive IRR.
    """
    irr = cf["IRR"].iloc[-1]
    net_gain = cf["Cumulative Net CF after all taxes"].iloc[-1]
    positive = np.flatnonzero(cf["IRR"].to_numpy() > 0)
    return {
        "xirr": None if irr == -1 else irr,
        "net_multiple": net_gain / total_investment + 1,
        "net_gain": net_gain,
        "payback_month": int(positive[0]) if len(positive) else None,
    }


def waterfall_steps(cf, total_investment):
    """Gross collections down to the net gain; each step's amounts sum to the final result."""
    steps = [
        ("Interest", cf["Interest Paid"].sum(), "Inflow"),
        ("Principal", cf["Principal Paid"].sum(), "Inflow"),
        ("WHT", cf["WHT on Loan Interest"].sum(), "Deduction"),
        ("Agent fee", -cf["Agent Fee"].sum(), "Deduction"),
        ("Income tax", -cf["Income tax (CIT)"].sum(), "Deduction"),
        ("SICAV costs", -cf["SICAV Costs"].sum(), "Deduction"),
        ("Investment", -total_investment, "Deduction"),
    ]
    rows = []
    level = 0.0
    for name, amount, kind in steps:
        if name == "Income tax" and abs(amount) < 0.5:
            continue  # tax is switched off in the model; skip the empty step
        rows.append({"Step": name, "Amount": amount, "Start": level, "End": level + amount, "Type": kind})
        level += amount
    rows.append({"Step": "Net gain", "Amount": level, "Start": 0.0, "End": level, "Type": "Result"})
    return pd.DataFrame(rows)


def fees_by_year(cf, funding_year, upfront_fees):
    """Agent fee per calendar year, plus the upfront (engagement + arrangement) fees in the funding year."""
    years = pd.to_datetime(cf["Month (calendar)"]).dt.year
    agent = cf["Agent Fee"].fillna(0).groupby(years).sum()
    out = pd.DataFrame({"Year": agent.index.astype(int), "Agent fee": agent.to_numpy()})
    out["Upfront fees"] = np.where(out["Year"] == funding_year, upfront_fees, 0.0)
    return out


# --- what-if transforms of the repayment table (only Month, Interest Paid and Principal Paid feed the model) ---

def _schedule(gc):
    return gc[["Month (calendar)", "Interest Paid", "Principal Paid"]].reset_index(drop=True)


def delay_payments(gc, months):
    """Every payment arrives `months` later, without extra interest."""
    gc = _schedule(gc)
    if months <= 0:
        return gc
    first = gc["Month (calendar)"].iloc[0]
    total = len(gc) + months
    out = pd.DataFrame({"Month (calendar)": [end_of_month(first, i) for i in range(total)]})
    for col in ("Interest Paid", "Principal Paid"):
        values = np.zeros(total)
        values[0] = np.nan
        values[1 + months:] = gc[col].to_numpy()[1:]
        out[col] = values
    return out


def principal_loss(gc, loss_share):
    """Only (1 - loss_share) of each principal repayment is recovered."""
    gc = _schedule(gc).copy()
    gc["Principal Paid"] = gc["Principal Paid"] * (1 - loss_share)
    return gc


def interest_at_maturity(gc):
    """All interest is paid in the last month instead of along the way."""
    gc = _schedule(gc).copy()
    total = np.nansum(gc["Interest Paid"].to_numpy()[1:])
    gc.loc[1:, "Interest Paid"] = 0.0
    gc.loc[gc.index[-1], "Interest Paid"] = total
    return gc
