from __future__ import annotations
import ast
from dataclasses import dataclass
from datetime import datetime
import json
import sys
import traceback
from prettytable import PrettyTable
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, MappedAsDataclass, mapped_column
from .core import (
    Base,
    Database,
    IpAddr,
    PKey,
    Str255,
    Str2048,
    iso8601_Z,
    longint,
    one_day_ago,
)


class ApacheEvent(MappedAsDataclass, Base):
    __tablename__ = "apache_access"

    id: Mapped[PKey] = mapped_column(init=False)
    timestamp: Mapped[datetime]
    host: Mapped[Str255]
    port: Mapped[int]
    src_addr: Mapped[IpAddr]
    authuser: Mapped[Str255]
    bytesin: Mapped[int]
    bytesout: Mapped[int]
    microsecs: Mapped[int] = mapped_column(sa.BigInteger)
    status: Mapped[int]
    reqline: Mapped[Str2048]
    method: Mapped[Str255]
    path: Mapped[Str2048]
    protocol: Mapped[Str255]
    referer: Mapped[Str2048]
    user_agent: Mapped[Str2048]


@dataclass
class ApacheAccess:
    db: Database

    def insert(self, event: ApacheEvent) -> None:
        self.db.add(event)

    def daily_report(self) -> str:
        report = "Website activity in the past 24 hours:\n"
        tbl = PrettyTable(["Hits", "Request"])
        tbl.align["Hits"] = "r"
        tbl.align["Request"] = "l"
        bytesIn = 0
        bytesOut = 0
        for reqline, qty, byin, byout in self.db.session.execute(
            sa.select(
                ApacheEvent.reqline,
                # func.count() [lowercase!] == COUNT(*)
                sa.func.count().label("qty"),
                sa.func.SUM(ApacheEvent.bytesin),
                sa.func.SUM(ApacheEvent.bytesout),
            )
            .where(ApacheEvent.timestamp >= one_day_ago())
            .group_by(ApacheEvent.reqline)
            .order_by(sa.desc("qty"), sa.asc(ApacheEvent.reqline))
        ):
            tbl.add_row([qty, reqline])
            bytesIn += byin
            bytesOut += byout
        report += tbl.get_string() + "\n"
        s_bytesIn = longint(bytesIn)
        s_bytesOut = longint(bytesOut)
        width = max(len(s_bytesIn), len(s_bytesOut))
        report += "Total bytes sent:     %*s\n" "Total bytes received: %*s\n" % (
            width,
            s_bytesOut,
            width,
            s_bytesIn,
        )
        return report


def main() -> None:
    # Apache log format:
    # "%{%Y-%m-%d %H:%M:%S %z}t|%v|%p|%a|%I|%O|%D|%>s|[\"%u\", \"%r\", \"%m\",
    #  \"%U%q\", \"%H\", \"%{Referer}i\", \"%{User-Agent}i\"]"
    line = None
    try:
        with Database.connect() as db:
            tbl = ApacheAccess(db)
            # `for line in sys.stdin` cannot be used here because Python
            # buffers stdin when iterating over it, causing the script to wait
            # for some too-large number of lines to be passed to it until it'll
            # do anything.
            for line in iter(sys.stdin.readline, ""):
                (
                    timestamp,
                    host,
                    port,
                    src_addr,
                    bytesIn,
                    bytesOut,
                    microsecs,
                    status,
                    strs,
                ) = line.split("|", 8)
                authuser, reqline, method, path, protocol, referer, user_agent = map(
                    reencode, ast.literal_eval(strs)
                )
                tbl.insert(
                    ApacheEvent(
                        timestamp=datetime.fromisoformat(timestamp),
                        host=host,
                        port=int(port),
                        src_addr=src_addr,
                        authuser=authuser,
                        bytesin=int(bytesIn),
                        bytesout=int(bytesOut),
                        microsecs=int(microsecs),
                        status=int(status),
                        reqline=reqline,
                        method=method,
                        path=path,
                        protocol=protocol,
                        referer=referer,
                        user_agent=user_agent,
                    )
                )
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


def reencode(s: str) -> str:
    return s.encode("iso-8859-1").decode("utf-8")


if __name__ == "__main__":
    main()
