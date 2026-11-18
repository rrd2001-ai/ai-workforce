from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database.db import Base


class EmailMessage(Base):

    __tablename__ = "email_messages"

    id = Column(Integer, primary_key=True, index=True)

    gmail_message_id = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    thread_id = Column(String(255), nullable=False, index=True)

    sender_email = Column(String(255), nullable=False)

    subject = Column(Text, nullable=True)

    body = Column(Text, nullable=True)

    task_id = Column(
        String(36),
        ForeignKey("tasks.task_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    processing_status = Column(
        String(30),
        default="received",
        nullable=False,
    )

    pending_reply = Column(Text, nullable=True)

    reply_status = Column(
        String(30),
        default="not_ready",
        nullable=False,
    )

    sent_message_id = Column(String(255), nullable=True)

    received_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
