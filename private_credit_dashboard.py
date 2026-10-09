import streamlit as st

from state import keep_inputs

st.set_page_config(
    page_title="Intro", layout="wide"
)
keep_inputs()

st.title(":red[_Private credit_]")

st.write("start w/ data upload")

st.sidebar.success("Choose page")
