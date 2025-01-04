from __future__ import annotations
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email import message_from_bytes, policy
from email.headerregistry import Address
import subprocess
import sys
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, MappedAsDataclass, mapped_column, relationship
from .core import Base, Database, PKey, Str2048, iso8601_Z, one_day_ago


class Contact(Base):
    __tablename__ = "inbox_contacts"
    __table_args__ = (sa.UniqueConstraint("realname", "email_address"),)

    id: Mapped[PKey] = field(init=False)
    realname: Mapped[Str2048]
    email_address: Mapped[Str2048]

    def __str__(self) -> str:
        # email.utils.formataddr performs an undesirable encoding of non-ASCII
        # characters
        return str(Address(self.realname, addr_spec=self.email_address))


class ToCC(MappedAsDataclass, Base):
    __tablename__ = "inbox_tocc"
    __table_args__ = (sa.UniqueConstraint("msg_id", "contact_id"),)

    msg_id: Mapped[PKey] = mapped_column(
        sa.ForeignKey("inbox.id", ondelete="CASCADE"), init=False
    )
    contact_id: Mapped[PKey] = mapped_column(
        sa.ForeignKey("inbox_contacts.id", ondelete="CASCADE"), init=False
    )


class EMail(Base):
    __tablename__ = "inbox"

    id: Mapped[PKey] = field(init=False)
    timestamp: Mapped[datetime]
    subject: Mapped[Str2048]
    sender_id: Mapped[int] = mapped_column(
        sa.ForeignKey("inbox_contacts.id", ondelete="CASCADE"), init=False
    )
    sender: Mapped[Contact] = relationship(init=False)
    size: Mapped[int]
    date: Mapped[datetime]
    tocc: Mapped[Contact] = relationship(secondary=ToCC)


@dataclass
class MailLog:
    db: Database

    def get_contact(self, contact: Address) -> Contact:
        cnobj = self.db.session.scalar(
            sa.select(Contact)
            .filter(Contact.realname == contact.display_name)
            .filter(Contact.email_address == contact.addr_spec)
        )
        if cnobj is None:
            cnobj = Contact(
                realname=contact.display_name,
                email_address=contact.addr_spec,
            )
            self.db.add(cnobj)
        return cnobj

    def insert_entry(
        self,
        subject: str,
        sender: Address,
        date: datetime,
        recipients: Iterable[Address],
        size: int,
    ) -> None:
        self.db.add(
            EMail(
                timestamp=datetime.now(timezone.utc).astimezone(),
                subject=subject[:2048],
                sender=self.get_contact(sender),
                size=size,
                date=date,
                tocc=list(set(map(self.get_contact, recipients))),
            )
        )

    def daily_report(self) -> str:
        title = "E-mails received in the past 24 hours:"
        newmail = list(
            self.db.session.scalars(
                sa.select(EMail)
                .filter(EMail.timestamp >= one_day_ago())
                .order_by(sa.asc(EMail.timestamp), sa.asc(EMail.id))
            )
        )
        if not newmail:
            return title + " none\n"
        report = title + "\n---\n"
        dests = set(
            subprocess.check_output(
                ["postconf", "-hx", "mydestination"],
                universal_newlines=True,
            )
            .strip()
            .lower()
            .split(", ")
        )
        for msg in newmail:
            recips = [c for c in msg.tocc if c.email_address.partition("@")[2] in dests]
            recips.sort(key=lambda c: (c.realname, c.email_address))
            report += (
                f"From:    {msg.sender}\n"
                f'To:      {", ".join(map(str, recips))}\n'
                f"Subject: {msg.subject}\n"
                f"Date:    {msg.date.astimezone(timezone.utc):%Y-%m-%dT%H:%M:%SZ}\n"
                f"Size:    {msg.size}\n"
                "---\n"
            )
        return report


def main():
    try:
        rawmsg = sys.stdin.buffer.read()
        size = len(rawmsg)
        msg = message_from_bytes(rawmsg, policy=policy.default)
        recipients = ()
        for fieldname in ("To", "CC"):
            if fieldname in msg:
                recipients += msg[fieldname].addresses
        with Database.connect() as db, MailLog(db) as tbl:
            tbl.insert_entry(
                subject=msg["Subject"] or "NO SUBJECT",
                sender=msg["From"].addresses[0],
                date=msg["Date"].datetime,
                recipients=recipients,
                size=size,
            )
    except Exception:
        ### TODO: Include a description of the e-mail?
        ### (Message-ID, first few characters, ???)
        print(f"\n{iso8601_Z()}: Error processing e-mail", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
