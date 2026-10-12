"""Save the current model to the database and load saved ones back into the app."""
from datetime import date, datetime

import pandas as pd
import streamlit as st

import db
from analysis import ANNUAL_INTEREST_RATE, TAX_RATE, deal_metrics
from state import INPUT_DEFAULTS, cached_model, model_inputs
from utils import get_repayment_table

# Version of the saved inputs document; bump it when its layout changes so old saves can be migrated
SCHEMA_VERSION = 1
DATE_KEYS = {"funding_date", "maturity_date"}


@st.cache_resource(show_spinner=False)
def get_engine():
    """Database engine from .streamlit/secrets.toml (written by init_db.py), or None if not set up.

    Creating it does not connect yet, so pages with a save button stay fast when the database is down.
    """
    try:
        cfg = dict(st.secrets["mysql"])
    except Exception:
        return None
    return db.make_engine(**cfg)


def engine_or_message(container):
    """The engine, or None after telling the user why the database cannot be used."""
    try:
        engine = get_engine()
    except Exception as e:
        container.error(f"Cannot reach the database: {getattr(e, 'orig', e)}")
        return None
    if engine is None:
        container.info("The database is not set up yet: run `python3 init_db.py` on the server, "
                       "then restart the dashboard.")
    return engine


def _plain(value):
    """JSON-friendly copy of a widget or table value."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _schedule_rows(df):
    return [{"date": _plain(d), "amount": None if _plain(a) is None else str(a)}
            for d, a in zip(df["Date"], df["Amount*"])]


def _schedule_df(rows):
    return pd.DataFrame({
        "Date": [date.fromisoformat(r["date"]) if r["date"] else None for r in rows],
        "Amount*": [r["amount"] for r in rows],
    })


def collect_inputs():
    """Everything needed to rebuild the current model exactly."""
    s = st.session_state
    return {
        "schema_version": SCHEMA_VERSION,
        **{key: _plain(s[key]) for key in INPUT_DEFAULTS},
        "interest_schedule": _schedule_rows(s.interest_df),
        "principal_schedule": _schedule_rows(s.principal_df),
        # Fixed in the app today; stored so a later change in the app cannot silently alter old saves
        "tax_rate": TAX_RATE,
        "annual_interest_rate": ANNUAL_INTEREST_RATE,
    }


def current_results():
    cf, _, _ = cached_model(st.session_state.repayment_df, **model_inputs())
    total = model_inputs()["total_investment"]
    m = deal_metrics(cf, total)
    return {
        "total_investment": float(total),
        "xirr": None if m["xirr"] is None else float(m["xirr"]),
        "net_multiple": float(m["net_multiple"]),
        "net_gain": float(m["net_gain"]),
        "payback_month": m["payback_month"],
    }


def apply_inputs(saved):
    """Load a saved inputs document into the app (call from a button callback, before widgets render)."""
    s = st.session_state
    for key, default in INPUT_DEFAULTS.items():
        value = saved.get(key, default)
        if key in DATE_KEYS:
            value = date.fromisoformat(value)
        elif value is not None:
            value = type(default)(value)
        s[key] = value
    s.interest_rate = s.interest_rate_pct / 100

    s.interest_df = s.interest_base = _schedule_df(saved["interest_schedule"])
    s.principal_df = s.principal_base = _schedule_df(saved["principal_schedule"])
    # Drop pending table edits so the Loan terms page shows the loaded schedules
    s.pop("editor_interest", None)
    s.pop("editor_principal", None)

    s.repayment_df = get_repayment_table(s.funding_amount, s.interest_rate, s.interest_df, s.principal_df,
                                         s.maturity_date, s.funding_date)


def save_controls(container, key):
    """'Save to database' form; `key` keeps widget keys unique per page."""
    engine = engine_or_message(container)
    if engine is None:
        return
    s = st.session_state
    if "repayment_df" not in s or s.repayment_df.empty:
        container.caption("Fill in the loan terms to be able to save.")
        return

    name = str(s.project_name).strip()
    if name in ("", "n/a"):
        container.caption("Set a project name on the Summary page to be able to save.")
    container.text_input("Saved by", key="saved_by")
    comment = container.text_input("Comment (optional)", key=f"{key}_comment", max_chars=500)
    if container.button("💾 Save to database", key=f"{key}_save", disabled=name in ("", "n/a")):
        try:
            version = db.save_model(engine, name, collect_inputs(), current_results(), s.saved_by.strip(), comment)
        except Exception as e:
            container.error(f"Saving failed: {getattr(e, 'orig', e)}")
        else:
            container.success(f"Saved **{name}** as version {version}.")
