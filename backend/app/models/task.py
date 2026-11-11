
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text, JSON

from app.database.db import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)

    task_id = Column(String(36), unique=True, index=True, nullable=False)

    user_task = Column(Text, nullable=False)

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

