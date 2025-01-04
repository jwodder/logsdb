from __future__ import annotations
from dataclasses import InitVar, dataclass, field
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time
from types import TracebackType
from typing import Annotated, Any
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import DeclarativeBase, Session, mapped_column, registry

JWODDER_ROOT = Path(__file__).parents[2]

PKey = Annotated[int, mapped_column(primary_key=True)]
Str255 = Annotated[str, mapped_column(sa.Unicode(255))]
Str2048 = Annotated[str, mapped_column(sa.Unicode(2048))]
IpAddr = Annotated[str, mapped_column(INET)]


class Base(DeclarativeBase):
    registry = registry(type_annotation_map={datetime: sa.DateTime(timezone=True)})


@dataclass
class Database:
    engine: InitVar[sa.Engine]
    session: Session = field(init=False)

    def __post_init__(self, engine: sa.Engine) -> None:
        Base.metadata.create_all(engine)
        self.session = Session(engine)

    @classmethod
    def connect(cls) -> Database:
        creds = json.loads((JWODDER_ROOT / "etc" / "logsdb.json").read_text())
        engine = sa.create_engine(
            sa.engine.URL.create(
                drivername="postgresql",
                host="localhost",
                database=creds["database"],
                username=creds["username"],
                password=creds["password"],
            )
        )
        return cls(engine)

    def __enter__(self) -> Database:
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> None:
        self.session.close()

    def add(self, obj: Any) -> None:
        self.session.add(obj)
        self.session.commit()


def longint(n: int) -> str:
    ns = str(n)
    nl = len(ns)
    triples = [ns[i : i + 3] for i in range(nl % 3, nl, 3)]
    if nl % 3:
        triples = [ns[: nl % 3]] + triples
    return " ".join(triples)


def one_day_ago() -> datetime:
    return datetime.now(timezone.utc).astimezone() - timedelta(days=1)


def iso8601_Z() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
