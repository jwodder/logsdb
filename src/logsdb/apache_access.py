from __future__ import annotations
import ast
import json
import sys
import traceback
from prettytable import PrettyTable
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import INET
from .core import SchemaConn, connect, iso8601_Z, longint, one_day_ago

### TODO: Is there any reason not to define these at module level?
schema = sa.MetaData()

apache_access = sa.Table(
    "apache_access",
    schema,
    sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    sa.Column("host", sa.Unicode(255), nullable=False),
    sa.Column("port", sa.Integer, nullable=False),
    sa.Column("src_addr", INET, nullable=False),
    sa.Column("authuser", sa.Unicode(255), nullable=False),
    sa.Column("bytesin", sa.Integer, nullable=False),
    sa.Column("bytesout", sa.Integer, nullable=False),
    sa.Column("microsecs", sa.BigInteger, nullable=False),
    sa.Column("status", sa.Integer, nullable=False),
    sa.Column("reqline", sa.Unicode(2048), nullable=False),
    sa.Column("method", sa.Unicode(255), nullable=False),
    sa.Column("path", sa.Unicode(2048), nullable=False),
    sa.Column("protocol", sa.Unicode(255), nullable=False),
    sa.Column("referer", sa.Unicode(2048), nullable=False),
    sa.Column("user_agent", sa.Unicode(2048), nullable=False),
)


class ApacheAccess(SchemaConn):
    SCHEMA = schema

    def insert_entry(
        self,
        timestamp,
        host,
        port,
        src_addr,
        authuser,
        bytesin,
        bytesout,
        microsecs,
        status,
        reqline,
        method,
        path,
        protocol,
        referer,
        user_agent,
    ):
        self.conn.execute(
            apache_access.insert().values(
                timestamp=timestamp,
                host=host,
                port=port,
                src_addr=src_addr,
                authuser=authuser,
                bytesin=bytesin,
                bytesout=bytesout,
                microsecs=microsecs,
                status=status,
                reqline=reqline,
                method=method,
                path=path,
                protocol=protocol,
                referer=referer,
                user_agent=user_agent,
            )
        )

    def daily_report(self):
        report = "Website activity in the past 24 hours:\n"
        tbl = PrettyTable(["Hits", "Request"])
        tbl.align["Hits"] = "r"
        tbl.align["Request"] = "l"
        bytesIn = 0
        bytesOut = 0
        for reqline, qty, byin, byout in self.conn.execute(
            sa.select(
                [
                    apache_access.c.reqline,
                    # func.count() [lowercase!] == COUNT(*)
                    sa.func.count().label("qty"),
                    sa.func.SUM(apache_access.c.bytesin),
                    sa.func.SUM(apache_access.c.bytesout),
                ]
            )
            .where(apache_access.c.timestamp >= one_day_ago())
            .group_by(apache_access.c.reqline)
            .order_by(sa.desc("qty"), sa.asc(apache_access.c.reqline))
        ):
            tbl.add_row([qty, reqline])
            bytesIn += byin
            bytesOut += byout
        report += tbl.get_string() + "\n"
        bytesIn = longint(bytesIn)
        bytesOut = longint(bytesOut)
        width = max(len(bytesIn), len(bytesOut))
        report += "Total bytes sent:     %*s\n" "Total bytes received: %*s\n" % (
            width,
            bytesOut,
            width,
            bytesIn,
        )
        return report


def main():
    # Apache log format:
    # "%{%Y-%m-%d %H:%M:%S %z}t|%v|%p|%a|%I|%O|%D|%>s|[\"%u\", \"%r\", \"%m\", \"%U%q\", \"%H\", \"%{Referer}i\", \"%{User-Agent}i\"]"
    line = None
    try:
        with ApacheAccess(connect()) as db:
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
                db.insert_entry(
                    timestamp=timestamp,
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


def reencode(s):
    return s.encode("iso-8859-1").decode("utf-8")


if __name__ == "__main__":
    main()
