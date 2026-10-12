import streamlit as st

from state import keep_inputs

st.set_page_config(
    page_title="Intro", layout="wide"
)
keep_inputs()

st.title(":red[_Private credit_]")

st.write(
    "This tool models a single private credit loan. From the loan terms it builds the monthly repayment "
    "schedule and the investor's cash flows after withholding tax, agent fee and SICAV costs, and calculates "
    "the return (XIRR), net multiple, net gain and payback period. Models can be exported to Excel and saved "
    "to the database."
)

st.warning(
    "**No warranty.** This tool is provided as is, without warranty of any kind. Its results are estimates "
    "based on the inputs entered and on simplifying assumptions, and are not investment, tax or legal advice. "
    "Always check the outputs, and consult the responsible colleagues or advisers where needed, before relying "
    "on them for any decision.",
    icon="⚠️",
)

st.header(":blue[How to use it]")

steps = [
    ("pages/1_first_page.py", "Loan terms",
     "Enter the loan amount, funding and maturity dates, interest rate and how often interest is paid. "
     "Edit the interest and principal schedules if the loan has partial payments or amortisation. "
     "The page shows the resulting monthly repayment schedule."),
    ("pages/2_Summary&CF.py", "Summary & CF",
     "Set the project name and assumptions: WHT, agent fee, SICAV costs, other costs and APS fees. "
     "The page shows the full cash flow, the NPV tables and the key results, and exports the model to Excel."),
    ("pages/3_Charts.py", "Charts",
     "Visual overview: cumulative cash flow and payback, where the money goes, outstanding balance and fees."),
    ("pages/4_Sensitivity.py", "Sensitivity",
     "XIRR at different interest rates when the loan is repaid earlier or later than planned, "
     "plus stress scenarios such as late payment or principal loss."),
    ("pages/5_Saved_models.py", "Saved models",
     "Save the current model as a new version in the database, or load a saved version back."),
]
for number, (page, label, text) in enumerate(steps, start=1):
    st.page_link(page, label=f"**{number}. {label}**")
    st.caption(text)

with st.expander("Calculation conventions"):
    st.markdown(
        "- Payments fall on month ends; a date within a month is paid at the end of that month.\n"
        "- Loan interest accrues monthly on the outstanding principal, using the days in the month over a "
        "360-day year. Interest not paid on an interest date is carried forward to the next one.\n"
        "- Returns are XIRR on the actual payment dates, after WHT, agent fee and SICAV costs. "
        "Income tax is currently set to zero.\n"
        "- SICAV costs are charged monthly (annual rate / 12) on the SICAV's outstanding balance.\n"
        "- Inputs are kept when switching pages, but are lost if the browser tab is reloaded or closed. "
        "Save the model to the database to keep it."
    )

st.sidebar.success("Choose a page above to start")
