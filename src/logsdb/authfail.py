#!/usr/bin/python3
import json
import re
import sys
import traceback
from prettytable import PrettyTable
import sqlalchemy as S
from sqlalchemy.dialects.postgresql import INET
from .core import SchemaConn, connect, iso8601_Z, one_day_ago

### TODO: Is there any reason not to define these at module level?
schema = S.MetaData()

authfail = S.Table(
    "authfail",
    schema,
    S.Column("timestamp", S.DateTime(timezone=True), nullable=False),
    S.Column("username", S.Unicode(255), nullable=False),
    S.Column("src_addr", INET, nullable=False),
)


class Authfail(SchemaConn):
    SCHEMA = schema

    def insert_entry(self, timestamp, username, src_addr):
        self.conn.execute(
            authfail.insert().values(
                timestamp=timestamp,
                username=username,
                src_addr=src_addr,
            )
        )

    def daily_report(self):
        tbl = PrettyTable(["Attempts", "IP Address"])
        tbl.align["Attempts"] = "r"
        tbl.align["IP Address"] = "l"
        for src_addr, qty in self.conn.execute(
            S.select([authfail.c.src_addr, S.func.COUNT("*").label("qty")])
            .where(authfail.c.timestamp >= one_day_ago())
            .group_by(authfail.c.src_addr)
            .order_by(S.desc("qty"), S.asc(authfail.c.src_addr))
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


def main():
    line = None
    try:
        with Authfail(connect()) as db:
            # `for line in sys.stdin` cannot be used here because Python
            # buffers stdin when iterating over it, causing the script to wait
            # for some too-large number of lines to be passed to it until it'll
            # do anything.
            for line in iter(sys.stdin.readline, ""):
                for rgx in MSG_REGEXEN:
                    m = rgx.fullmatch(line)
                    if m:
                        db.insert_entry(**m.groupdict())
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


if __name__ == "__main__":
    main()
