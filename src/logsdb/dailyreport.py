from __future__ import annotations
from email.message import EmailMessage
import json
import os
from pathlib import Path
from shutil import disk_usage
import socket
import subprocess
import sys
from .core import JWODDER_ROOT, Database, iso8601_Z, longint

RECIPIENT = "jwodder@gmail.com"
MAILBOX = Path("/home/jwodder/Mail/INBOX")
NETDEVICE = "eth0"
DISK_THRESHOLD = 50  # measured in percentage points
LOGS_DIR = JWODDER_ROOT / "logs"

TAGSEQ = "DISK LOGERR REBOOT MAIL".split()


def check_errlogs(tags: set[str]) -> str | None:
    errlogs = [p for p in LOGS_DIR.iterdir() if p.stat().st_size > 0]
    if errlogs:
        tags.add("LOGERR")
        return "The following files in {} are nonempty:\n{}".format(
            LOGS_DIR,
            "".join(map("    {0.name}\n".format, errlogs)),
        )
    else:
        return None


def check_load() -> str:
    with open("/proc/loadavg") as fp:
        return "Load: " + ", ".join(fp.read().split()[:3]) + "\n"


def check_disk(tags: set[str]) -> str:
    fssize, fsused, _ = disk_usage("/")
    sused = longint(fsused)
    ssize = longint(fssize)
    width = max(len(sused), len(ssize))
    pctused = 100 * fsused / fssize
    if pctused >= DISK_THRESHOLD:
        tags.add("DISK")
    return "Space used on root partition:\n    %*s\n  / %*s\n   (%f%%)\n" % (
        width,
        sused,
        width,
        ssize,
        pctused,
    )


def check_authfail(db: Database) -> str | None:
    try:
        from logsdb.authfail import Authfail
    except ImportError:
        return None
    return Authfail(db).daily_report()


def check_apache_access(db: Database) -> str | None:
    try:
        from logsdb.apache_access import ApacheAccess
    except ImportError:
        return None
    return ApacheAccess(db).daily_report()


def check_inbox(db: Database) -> str | None:
    try:
        from logsdb.maillog import MailLog
    except ImportError:
        return None
    return MailLog(db).daily_report()


def check_mailbox(tags: set[str]) -> None:
    if MAILBOX.exists() and MAILBOX.stat().st_size > 0:
        tags.add("MAIL")


def check_reboot(tags: set[str]) -> str | None:
    if Path("/var/run/reboot-required").exists():
        tags.add("REBOOT")
        try:
            with open("/var/run/reboot-required.pkgs") as fp:
                pkgs = fp.read().splitlines()
        except IOError:
            pkgs = []
        report = "Reboot required by the following packages:"
        if pkgs:
            report += "\n" + "".join("    " + s + "\n" for s in pkgs)
        else:
            report += " UNKNOWN\n"
        return report
    else:
        return None


def check_vnstat() -> str:
    vnstat = subprocess.check_output(
        ["vnstat", "--json", "d", "2", "-i", "eth0"],
        universal_newlines=True,
    )
    data = json.loads(vnstat)
    yesterday = data["interfaces"][0]["traffic"]["day"][0]
    sent = longint(yesterday["tx"])
    received = longint(yesterday["rx"])
    width = max(len(sent), len(received))
    return "Data sent yesterday:     %*s B\n" "Data received yesterday: %*s B\n" % (
        width,
        sent,
        width,
        received,
    )


def main() -> None:
    tags: set[str] = set()
    reports = []
    with Database.connect() as db:
        check_mailbox(tags)
        reports.append(check_errlogs(tags))
        reports.append(check_reboot(tags))
        reports.append(check_load())
        reports.append(check_disk(tags))
        reports.append(check_vnstat())
        reports.append(check_inbox(db))
        reports.append(check_authfail(db))
        reports.append(check_apache_access(db))
    body = "\n".join(r for r in reports if r is not None and r != "")
    if not body:
        body = "Nothing to report\n"
    subject = ""
    for t in TAGSEQ:
        if t in tags:
            subject += "[" + t + "] "
            tags.remove(t)
    for t in sorted(tags):
        subject += "[" + t + "] "
    subject += f"Status Report: {socket.gethostname()}, {iso8601_Z()}"
    if sys.stdout.isatty():
        # Something about typical dailyreport contents (the size? long lines?)
        # invariably causes serialized EmailMessage's to use quoted-printable
        # transfer encoding no matter what I do.  Thus, in order to actually be
        # able to view non-ASCII characters in subjects of recently-received
        # e-mails in `less`, we need to basically output a pseudo-e-email.
        subprocess.run(
            [os.environ.get("PAGER", "less")],
            input=f"Subject: {subject}\n\n{body}",
            encoding="utf-8",
        )
    else:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["To"] = RECIPIENT
        msg.set_content(body)
        print(str(msg))


if __name__ == "__main__":
    main()
