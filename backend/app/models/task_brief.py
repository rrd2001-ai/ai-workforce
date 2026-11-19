from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database.db import Base


class TaskBrief(Base):
    __tablename__ = "task_briefs"

    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "version",
            name="uq_task_brief_conversation_version",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=False,
    )

    version = Column(Integer, nullable=False, default=1)

    objective = Column(Text, nullable=False)

    requirements = Column(
        JSONB,
        nullable=False,
        default=list,
    )

    constraints = Column(
        JSONB,
        nullable=False,
        default=list,
    )

    expected_output = Column(Text, nullable=True)

    missing_information = Column(
        JSONB,
        nullable=False,
        default=list,
    )

    status = Column(
        String(30),
        nullable=False,
        default="draft",
    )

    confirmed_at = Column(DateTime(timezone=True), nullable=True)

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
