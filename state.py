from datetime import date

import streamlit as st

from analysis import run_model

# Inputs that should survive switching between pages, with their first-visit defaults.
# Do not add data_editor keys here: their state cannot be assigned.
INPUT_DEFAULTS = {
    # Loan terms
    "funding_amount": 0,
    "funding_date": date.today(),
    "maturity_date": date.today(),
    "interest_rate_pct": 0.0,
    "repayment_type": "lump-sum",
    # Summary & CF
    "project_name": "n/a",
    "wht_input": 0.0,
    "in_agent_fee": 0.0,
    "in_sicav": 3.0,
    "in_other_costs": 0,
    "eng_fee": 0,
    "arr_fee": 0,
}


def keep_inputs():
    """Keep widget values across pages; call at the top of every page.

    Streamlit drops a widget's value whenever its page is not shown. Re-assigning
    the key detaches it from the widget so it persists, and sets the default on
    the first visit.
    """
    for key, default in INPUT_DEFAULTS.items():
        st.session_state[key] = st.session_state.get(key, default)


def require_loan_terms():
    """Stop the page with a hint until the Loan terms page has produced a schedule."""
    if "repayment_df" not in st.session_state or st.session_state.repayment_df.empty:
        st.warning("⚠️ Please configure the 'Loan Terms' first to generate the base schedule.")
        st.stop()


def model_inputs():
    """Assumptions from the Summary page, converted as the Summary page does."""
    s = st.session_state
    return {
        "wht": s.wht_input / 100,
        "agent_fee": s.in_agent_fee / 100,
        "total_investment": s.in_other_costs + s.funding_amount,
        "sicav_costs_monthly": s.in_sicav / 100 / 12,
    }


# Model run cached on its inputs, shared by the Charts and Sensitivity pages
cached_model = st.cache_data(run_model, show_spinner=False)
