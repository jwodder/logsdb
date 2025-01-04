from __future__ import annotations
from email.message import EmailMessage
from pathlib import Path
import sys
import click
from . import __version__
from .config import Config


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "-c",
    "--config",
    "config_file",
    type=click.Path(exists=True, readable=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.version_option(
    __version__,
    "-V",
    "--version",
    message="%(prog)s %(version)s",
)
@click.pass_context
def main(ctx: click.Context, config_file: Path) -> None:
    ctx.obj = Config.from_ini_file(config_file)


@main.command()
@click.pass_obj
def apache_access(cfg: Config) -> None:
    from .apache_access import process_input

    with cfg.connect_to_database() as db:
        process_input(db)


@main.command()
@click.pass_obj
def authfail(cfg: Config) -> None:
    from .authfail import process_input

    with cfg.connect_to_database() as db:
        process_input(db)


@main.command()
@click.pass_obj
def maillog(cfg: Config) -> None:
    from .maillog import process_input

    with cfg.connect_to_database() as db:
        process_input(db)


@main.command()
@click.pass_obj
def dailyreport(cfg: Config) -> None:
    from .dailyreport import get_daily_report

    with cfg.connect_to_database() as db:
        report = get_daily_report(db, cfg)
    if sys.stdout.isatty():
        # Something about typical dailyreport contents (the size? long lines?)
        # invariably causes serialized EmailMessage's to use quoted-printable
        # transfer encoding no matter what I do.  Thus, in order to actually be
        # able to view non-ASCII characters in subjects of recently-received
        # e-mails in `less`, we need to basically output a pseudo-e-email.
        click.echo_via_pager(f"Subject: {report.subject}\n\n{report.body}".rstrip("\n"))
    else:
        msg = EmailMessage()
        msg["Subject"] = report.subject
        msg["To"] = cfg.dailyreport.recipient
        msg.set_content(report.body)
        print(str(msg))


if __name__ == "__main__":
    main()
