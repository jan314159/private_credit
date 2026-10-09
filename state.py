from datetime import date

import streamlit as st

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
