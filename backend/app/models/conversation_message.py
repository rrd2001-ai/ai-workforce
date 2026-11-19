from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database.db import Base


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    __table_args__ = (
        Index(
            "ix_conversation_messages_conversation_created",
            "conversation_id", "created_at", "id",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=False,
    )

    role = Column(String(20), nullable=False)

    content = Column(Text, nullable=False)

    message_type = Column(
        String(30),
        nullable=False,
        default="chat",
    )

    message_metadata = Column(
        "metadata",
        JSONB,
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
