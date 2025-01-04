from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
from shutil import disk_usage
import socket
import subprocess
from .config import Config
from .core import Database, iso8601_Z, longint

NETDEVICE = "eth0"
DISK_THRESHOLD = 50  # measured in percentage points

TAGSEQ = "DISK LOGERR REBOOT MAIL".split()


def check_errlogs(logs_dir: Path, tags: set[str]) -> str | None:
    errlogs = [p for p in logs_dir.iterdir() if p.stat().st_size > 0]
    if errlogs:
        tags.add("LOGERR")
        return "The following files in {} are nonempty:\n{}".format(
            logs_dir,
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
    from .authfail import Authfail

    return Authfail(db).daily_report()


def check_apache_access(db: Database) -> str | None:
    from .apache_access import ApacheAccess

    return ApacheAccess(db).daily_report()


def check_inbox(db: Database) -> str | None:
    from .maillog import MailLog

    return MailLog(db).daily_report()


def check_mailbox(mailbox: Path, tags: set[str]) -> None:
    if mailbox.exists() and mailbox.stat().st_size > 0:
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


@dataclass
class DailyReport:
    subject: str
    body: str


def get_daily_report(db: Database, cfg: Config) -> DailyReport:
    tags: set[str] = set()
    reports = []
    check_mailbox(cfg.dailyreport.mailbox, tags)
    reports.append(check_errlogs(cfg.dailyreport.logs_dir, tags))
    reports.append(check_reboot(tags))
    reports.append(check_load())
    reports.append(check_disk(tags))
    reports.append(check_vnstat())
    if cfg.features.maillog:
        reports.append(check_inbox(db))
    if cfg.features.authfail:
        reports.append(check_authfail(db))
    if cfg.features.apache_access:
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
    return DailyReport(subject, body)
