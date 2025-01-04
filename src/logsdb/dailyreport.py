#!/usr/bin/python3
from email.message import EmailMessage
from inspect import signature
import json
import os
from pathlib import Path
from shutil import disk_usage
import socket
import subprocess
import sys
from .core import JWODDER_ROOT, connect, iso8601_Z, longint

RECIPIENT = "jwodder@gmail.com"
MAILBOX = Path("/home/jwodder/Mail/INBOX")
NETDEVICE = "eth0"
DISK_THRESHOLD = 50  # measured in percentage points
LOGS_DIR = JWODDER_ROOT / "logs"

TAGSEQ = "DISK LOGERR REBOOT MAIL".split()


def check_errlogs(tags):
    errlogs = [p for p in LOGS_DIR.iterdir() if p.stat().st_size > 0]
    if errlogs:
        tags.add("LOGERR")
        return "The following files in {} are nonempty:\n{}".format(
            LOGS_DIR,
            "".join(map("    {0.name}\n".format, errlogs)),
        )


def check_load():
    with open("/proc/loadavg") as fp:
        return "Load: " + ", ".join(fp.read().split()[:3]) + "\n"


def check_disk(tags):
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


def check_authfail(engine):
    try:
        from jwodder_logsdb.authfail import Authfail
    except ImportError:
        return None
    with Authfail(engine) as db:
        return db.daily_report()


def check_apache_access(engine):
    try:
        from jwodder_logsdb.apache_access import ApacheAccess
    except ImportError:
        return None
    with ApacheAccess(engine) as db:
        return db.daily_report()


def check_inbox(engine):
    try:
        from jwodder_logsdb.maillog import MailLog
    except ImportError:
        return None
    with MailLog(engine) as db:
        return db.daily_report()


def check_mailbox(tags):
    if MAILBOX.exists() and MAILBOX.stat().st_size > 0:
        tags.add("MAIL")


def check_reboot(tags):
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


def check_vnstat():
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


def main():
    body = ""
    tags = set()
    engine = connect()
    for check in [
        check_mailbox,
        check_errlogs,
        check_reboot,
        check_load,
        check_disk,
        check_vnstat,
        check_inbox,
        check_authfail,
        check_apache_access,
    ]:
        kwargs = {}
        if "engine" in signature(check).parameters:
            kwargs["engine"] = engine
        if "tags" in signature(check).parameters:
            kwargs["tags"] = tags
        report = check(**kwargs)
        if report is not None and report != "":
            if body:
                body += "\n"
            body += report
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
