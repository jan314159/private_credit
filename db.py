"""Saved models in the MySQL `valuations` database (no Streamlit here).

Each save is a new version of a project; nothing is ever overwritten. The model inputs are stored
as one JSON document, plus a few headline results so saves can be listed and compared without
recalculating.
"""
import subprocess
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa

DB_DEFAULTS = {"host": "cz-cld-mysql01", "port": 3306, "database": "valuations", "username": "valuations"}

metadata = sa.MetaData()

models = sa.Table(
    "private_credit_models", metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("project_name", sa.String(255), nullable=False),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("saved_at", sa.DateTime, nullable=False),
    sa.Column("saved_by", sa.String(100)),
    sa.Column("comment", sa.String(500)),
    sa.Column("app_version", sa.String(40)),
    sa.Column("inputs", sa.JSON, nullable=False),
    sa.Column("total_investment", sa.Double),
    sa.Column("xirr", sa.Double),
    sa.Column("net_multiple", sa.Double),
    sa.Column("net_gain", sa.Double),
    sa.Column("payback_month", sa.Integer),
    sa.UniqueConstraint("project_name", "version", name="uq_project_version"),
    mysql_charset="utf8mb4",
)

SUMMARY_COLUMNS = [models.c.id, models.c.project_name, models.c.version, models.c.saved_at, models.c.saved_by,
                   models.c.comment, models.c.xirr, models.c.net_multiple, models.c.net_gain,
                   models.c.payback_month, models.c.total_investment]


def make_engine(password, host=None, port=None, database=None, username=None):
    # URL.create escapes the password, so characters like @ : / are safe
    url = sa.URL.create(
        "mysql+pymysql",
        username=username or DB_DEFAULTS["username"],
        password=password,
        host=host or DB_DEFAULTS["host"],
        port=int(port or DB_DEFAULTS["port"]),
        database=database or DB_DEFAULTS["database"],
        query={"charset": "utf8mb4"},
    )
    return sa.create_engine(url, pool_pre_ping=True, pool_recycle=3600, connect_args={"connect_timeout": 5})


def create_tables(engine):
    metadata.create_all(engine, checkfirst=True)


def app_version():
    """Short git commit of the running code, so a save records which model logic produced it."""
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=Path(__file__).parent,
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def save_model(engine, project_name, inputs, results, saved_by="", comment=""):
    """Store a new version of `project_name`; returns the version number."""
    for _ in range(3):  # retry if someone saved the same project at the same moment
        try:
            with engine.begin() as conn:
                latest = conn.execute(
                    sa.select(sa.func.max(models.c.version)).where(models.c.project_name == project_name)
                ).scalar()
                version = (latest or 0) + 1
                conn.execute(models.insert().values(
                    project_name=project_name,
                    version=version,
                    saved_at=datetime.now().replace(microsecond=0),
                    saved_by=saved_by or None,
                    comment=comment or None,
                    app_version=app_version(),
                    inputs=inputs,
                    **results,
                ))
            return version
        except sa.exc.IntegrityError:
            continue
    raise RuntimeError("Could not save: the project was being saved by someone else at the same time. Try again.")


def list_models(engine):
    """All saves, newest first, without the inputs document."""
    with engine.connect() as conn:
        rows = conn.execute(sa.select(*SUMMARY_COLUMNS).order_by(models.c.saved_at.desc(), models.c.id.desc()))
        return [dict(r._mapping) for r in rows]


def load_inputs(engine, model_id):
    with engine.connect() as conn:
        return conn.execute(sa.select(models.c.inputs).where(models.c.id == model_id)).scalar_one()
