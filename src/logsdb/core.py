from __future__ import annotations
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time
import sqlalchemy as sa

JWODDER_ROOT = Path(__file__).parents[2]


class SchemaConn:
    def __init__(self, engine):
        self.SCHEMA.create_all(engine)
        self.engine = engine
        self.conn = None

    def __enter__(self):
        self.conn = self.engine.connect()
        return self

    def __exit__(self, _exc_type, _exc_value, _exc_tb):
        self.conn.close()
        return False


def connect() -> Engine:
    creds = json.loads((JWODDER_ROOT / "etc" / "logsdb.json").read_text())
    return sa.create_engine(
        sa.engine.url.URL(
            drivername="postgresql",
            host="localhost",
            database=creds["database"],
            username=creds["username"],
            password=creds["password"],
        )
    )


def longint(n):
    n = str(n)
    nl = len(n)
    triples = [n[i : i + 3] for i in range(nl % 3, nl, 3)]
    if nl % 3:
        triples = [n[: nl % 3]] + triples
    return " ".join(triples)


def one_day_ago():
    return datetime.now(timezone.utc).astimezone() - timedelta(days=1)


def iso8601_Z():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
