from __future__ import annotations
from datetime import datetime, timezone
from email import message_from_bytes, policy
from email.headerregistry import Address
import subprocess
import sys
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from .core import connect, iso8601_Z, one_day_ago

Base = declarative_base()

inbox_tocc = sa.Table(
    "inbox_tocc",
    Base.metadata,
    sa.Column(
        "msg_id",
        sa.Integer,
        sa.ForeignKey("inbox.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "contact_id",
        sa.Integer,
        sa.ForeignKey("inbox_contacts.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.UniqueConstraint("msg_id", "contact_id"),
)


class Contact(Base):
    __tablename__ = "inbox_contacts"
    __table_args__ = (sa.UniqueConstraint("realname", "email_address"),)

    id = sa.Column(sa.Integer, primary_key=True, nullable=False)
    realname = sa.Column(sa.Unicode(2048), nullable=False)
    email_address = sa.Column(sa.Unicode(2048), nullable=False)

    def __str__(self):
        # email.utils.formataddr performs an undesirable encoding of non-ASCII
        # characters
        return str(Address(self.realname, addr_spec=self.email_address))


class EMail(Base):
    __tablename__ = "inbox"

    id = sa.Column(sa.Integer, primary_key=True, nullable=False)
    timestamp = sa.Column(sa.DateTime(timezone=True), nullable=False)
    subject = sa.Column(sa.Unicode(2048), nullable=False)
    sender_id = sa.Column(
        "sender",
        sa.Integer,
        sa.ForeignKey("inbox_contacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender = relationship("Contact")
    size = sa.Column(sa.Integer, nullable=False)
    date = sa.Column(sa.DateTime(timezone=True), nullable=False)
    tocc = relationship("Contact", secondary=inbox_tocc)


class MailLog:
    def __init__(self, engine):
        Base.metadata.create_all(engine)
        self.engine = engine
        self.session = None

    def __enter__(self):
        self.session = sessionmaker(bind=self.engine)()
        return self

    def __exit__(self, _exc_type, _exc_value, _exc_tb):
        self.session.close()
        return False

    def get_contact(self, contact):
        """
        :type contact: email.headerregistry.Address
        :return: Contact
        """
        cnobj = (
            self.session.query(Contact)
            .filter(Contact.realname == contact.display_name)
            .filter(Contact.email_address == contact.addr_spec)
            .first()
        )
        if cnobj is None:
            cnobj = Contact(
                realname=contact.display_name,
                email_address=contact.addr_spec,
            )
            self.session.add(cnobj)
        return cnobj

    def insert_entry(self, subject, sender, date, recipients, size):
        """
        :type subject: str
        :type sender: email.headerregistry.Address
        :type date: datetime.datetime
        :type recipients: Iterable[email.headerregistry.Address]
        :type size: int
        """
        self.session.add(
            EMail(
                timestamp=datetime.now(timezone.utc).astimezone(),
                subject=subject[:2048],
                sender=self.get_contact(sender),
                size=size,
                date=date,
                tocc=list(set(map(self.get_contact, recipients))),
            )
        )
        self.session.commit()

    def daily_report(self):
        title = "E-mails received in the past 24 hours:"
        newmail = (
            self.session.query(EMail)
            .filter(EMail.timestamp >= one_day_ago())
            .order_by(sa.asc(EMail.timestamp), sa.asc(EMail.id))
            .all()
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
        for field in ("To", "CC"):
            if field in msg:
                recipients += msg[field].addresses
        with MailLog(connect()) as db:
            db.insert_entry(
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
