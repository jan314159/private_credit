"""One-time database setup: python3 init_db.py

Asks for the MySQL password (not shown while typing), checks the connection, creates the
`private_credit_models` table if needed and stores the connection in .streamlit/secrets.toml,
readable only by the user running the app. The password never goes into git.
"""
import argparse
import getpass
import json
import os
import sys
import tomllib
from pathlib import Path

from db import DB_DEFAULTS, create_tables, make_engine

SECRETS = Path(__file__).parent / ".streamlit" / "secrets.toml"


def _toml(data):
    """Write nested dicts of strings/numbers as TOML (JSON string escaping is valid TOML)."""
    lines = [f"{k} = {json.dumps(v)}" for k, v in data.items() if not isinstance(v, dict)]
    for name, table in data.items():
        if isinstance(table, dict):
            lines += ["", f"[{name}]"] + [f"{k} = {json.dumps(v)}" for k, v in table.items()]
    return "\n".join(lines).lstrip() + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for key, default in DB_DEFAULTS.items():
        parser.add_argument(f"--{key}", default=default, type=type(default), help=f"default: {default}")
    args = vars(parser.parse_args())

    password = getpass.getpass(f"MySQL password for {args['username']}@{args['host']}/{args['database']}: ")
    if not password:
        sys.exit("No password given, nothing changed.")

    engine = make_engine(password, **args)
    try:
        create_tables(engine)
    except Exception as e:
        sys.exit(f"Could not connect or create the table: {e.__class__.__name__}: {getattr(e, 'orig', e)}")
    print("Connected, table private_credit_models is ready.")

    secrets = tomllib.loads(SECRETS.read_text()) if SECRETS.exists() else {}
    secrets["mysql"] = {**args, "password": password}
    SECRETS.parent.mkdir(exist_ok=True)
    fd = os.open(SECRETS, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(_toml(secrets))
    os.chmod(SECRETS, 0o600)
    print(f"Saved the connection to {SECRETS} (readable only by you). Restart the dashboard to use it.")


if __name__ == "__main__":
    main()
