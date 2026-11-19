from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, Index, String
from sqlalchemy.dialects.postgresql import UUID

from app.database.db import Base


class Conversation(Base):
    __tablename__ = "conversations"

    __table_args__ = (
        Index("ix_conversations_created_at", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    title = Column(String(200), nullable=True)

    status = Column(
        String(30),
        nullable=False,
        default="active",
    )

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
