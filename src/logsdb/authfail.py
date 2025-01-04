from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
import json
import re
import sys
import traceback
from prettytable import PrettyTable
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, MappedAsDataclass, mapped_column
from .core import Base, Database, IpAddr, PKey, Str255, iso8601_Z, one_day_ago


class AuthfailEvent(MappedAsDataclass, Base):
    __tablename__ = "authfail"

    id: Mapped[PKey] = mapped_column(init=False)
    timestamp: Mapped[datetime]
    username: Mapped[Str255]
    src_addr: Mapped[IpAddr]


@dataclass
class Authfail:
    db: Database

    def insert(self, event: AuthfailEvent) -> None:
        self.db.add(event)

    def daily_report(self) -> str:
        tbl = PrettyTable(["Attempts", "IP Address"])
        tbl.align["Attempts"] = "r"
        tbl.align["IP Address"] = "l"
        for src_addr, qty in self.db.session.execute(
            sa.select(AuthfailEvent.src_addr, sa.func.COUNT("*").label("qty"))
            .where(AuthfailEvent.timestamp >= one_day_ago())
            .group_by(AuthfailEvent.src_addr)
            .order_by(sa.desc("qty"), sa.asc(AuthfailEvent.src_addr))
        ):
            tbl.add_row([qty, src_addr])
        return (
            "Failed SSH login attempts in the past 24 hours:\n"
            + tbl.get_string()
            + "\n"
        )


MSG_REGEXEN = [
    re.compile(
        r"(?P<timestamp>\S+) \S+ sshd\[\d+\]:"
        r"(?: message repeated \d+ times: \[)?"
        r" Failed (?:password|keyboard-interactive/pam|none)"
        r" for (?:invalid user )?(?P<username>.+?)"
        r" from (?P<src_addr>\S+) port \d+ ssh2\]?\s*"
    ),
    re.compile(
        r"(?P<timestamp>\S+) \S+ sshd\[\d+\]:"
        r"(?: message repeated \d+ times: \[)?"
        r" Invalid user (?P<username>.*?)"
        r" from (?P<src_addr>\S+) port \d+\s*",
    ),
]


def process_input(db: Database) -> None:
    line = None
    try:
        tbl = Authfail(db)
        # `for line in sys.stdin` cannot be used here because Python buffers
        # stdin when iterating over it, causing the script to wait for some
        # too-large number of lines to be passed to it until it'll do anything.
        for line in iter(sys.stdin.readline, ""):
            for rgx in MSG_REGEXEN:
                if m := rgx.fullmatch(line):
                    tbl.insert(
                        AuthfailEvent(
                            timestamp=datetime.fromisoformat(m["timestamp"]),
                            username=m["username"],
                            src_addr=m["src_addr"],
                        )
                    )
                    break
            else:
                raise ValueError("Could not parse logfile entry")
    except Exception as e:
        print(
            json.dumps(
                {
                    "time": iso8601_Z(),
                    "line": line,
                    # "about": about,
                    "traceback": traceback.format_exc(),
                    "error_type": type(e).__name__,
                    "error": str(e),
                }
            ),
            file=sys.stderr,
            flush=True,
        )
        sys.exit(1)
