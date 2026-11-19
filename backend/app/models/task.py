
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    Index,
    String,
    Text,
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.database.db import Base


class Task(Base):
    __tablename__ = "tasks"

    __table_args__ = (
        Index("ix_tasks_created_at", "created_at"),
        Index(
            "ix_tasks_conversation_created",
            "conversation_id", "created_at",
        ),
    )

    id = Column(Integer, primary_key=True)

    task_id = Column(String(36), unique=True, index=True, nullable=False)

    user_task = Column(Text, nullable=False)

    # Conversation and confirmed task brief
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=False,
    )

    task_brief_id = Column(
        UUID(as_uuid=True),
        ForeignKey("task_briefs.id", ondelete="SET NULL"),
        nullable=True,
        index=False,
    )

    # Master-selected execution route
    execution_route = Column(String(20), nullable=True)

    # Human approval for external actions
    requires_human_approval = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=sql_text("false"),
    )

    human_approval_status = Column(
        String(30),
        nullable=False,
        default="not_required",
        server_default=sql_text("'not_required'"),
    )

    execution_plan = Column(JSON, nullable=True)

    worker_assignment = Column(Text, nullable=True)

    acceptance_criteria = Column(Text, nullable=True)

    worker_output = Column(Text, nullable=True)

    review_feedback = Column(Text, nullable=True)

    review_status = Column(String(20), default="pending")

    retry_count = Column(Integer, default=0)

    execution_status = Column(String(20), default="planning")

    final_output = Column(Text, nullable=True)

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
