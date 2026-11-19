from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID

from app.database.db import Base


class UserMemory(Base):
    __tablename__ = "user_memories"

    __table_args__ = (
        Index(
            "uq_user_memories_global_key",
            "memory_key",
            unique=True,
            postgresql_where=text("source_conversation_id IS NULL"),
        ),
        Index(
            "uq_user_memories_conversation_key",
            "source_conversation_id",
            "memory_key",
            unique=True,
            postgresql_where=text("source_conversation_id IS NOT NULL"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    memory_key = Column(String(200), nullable=False, index=True)

    memory_value = Column(Text, nullable=False)

    memory_type = Column(
        String(40),
        nullable=False,
    )

    source_conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    importance = Column(Integer, nullable=False, default=5)

    is_active = Column(Boolean, nullable=False, default=True)

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
