import pandas as pd
import streamlit as st

import db
from model_store import apply_inputs, engine_or_message, save_controls
from state import keep_inputs

st.set_page_config(layout="wide", page_title="Saved models")
keep_inputs()

st.title(":red[_Saved models_]")

engine = engine_or_message(st)
if engine is None:
    st.stop()

# ---------------------------------------------------------------- save
st.header(":blue[Save current model]")
st.caption(f"Saves everything needed to rebuild the model as a new version of project "
           f"**{st.session_state.project_name}** (set the project name on the Summary page). "
           "Earlier versions are kept.")
save_controls(st.container(), "page")

# ---------------------------------------------------------------- load
st.header(":blue[Load a saved model]")

try:
    saves = pd.DataFrame(db.list_models(engine))
except Exception as e:
    st.error(f"Could not read saved models: {getattr(e, 'orig', e)}")
    st.stop()

if saves.empty:
    st.info("Nothing saved yet.")
    st.stop()

projects = list(dict.fromkeys(saves["project_name"]))  # most recently saved first
c1, c2 = st.columns(2)
project = c1.selectbox("Project", projects)
versions = saves[saves["project_name"] == project].sort_values("version", ascending=False)


def describe(row):
    parts = [f"v{row.version}", row.saved_at.strftime("%Y-%m-%d %H:%M")]
    parts += [p for p in (row.saved_by, row.comment) if p]
    return " · ".join(parts)


labels = {row.id: describe(row) for row in versions.itertuples()}
model_id = c2.selectbox("Version", list(labels), format_func=labels.get)


def load(model_id):
    try:
        apply_inputs(db.load_inputs(engine, model_id))
    except Exception as e:
        st.session_state.load_message = ("error", f"Loading failed: {getattr(e, 'orig', e)}")
    else:
        st.session_state.load_message = ("success", f"Loaded {project}: {labels[model_id]}.")


st.button("📂 Load this version", type="primary", on_click=load, args=(model_id,))

if "load_message" in st.session_state:
    kind, text = st.session_state.pop("load_message")
    getattr(st, kind)(text)
    if kind == "success":
        st.page_link("pages/1_first_page.py", label="Open Loan terms", icon="➡️")
        st.page_link("pages/2_Summary&CF.py", label="Open Summary & CF", icon="➡️")

st.subheader(f"All versions of {project}")
st.dataframe(
    versions.drop(columns=["id", "project_name"]).round({"net_gain": 0, "total_investment": 0}),
    hide_index=True,
    width="stretch",
    column_config={
        "version": st.column_config.NumberColumn("Version", format="v%d"),
        "saved_at": st.column_config.DatetimeColumn("Saved at", format="YYYY-MM-DD HH:mm"),
        "saved_by": "Saved by",
        "comment": "Comment",
        "xirr": st.column_config.NumberColumn("XIRR", format="percent"),
        "net_multiple": st.column_config.NumberColumn("Net multiple", format="%.2fx"),
        "net_gain": st.column_config.NumberColumn("Net gain", format="localized"),
        "payback_month": st.column_config.NumberColumn("Payback (month)"),
        "total_investment": st.column_config.NumberColumn("Total investment", format="localized"),
    },
)
