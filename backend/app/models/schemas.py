from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Literal
from datetime import datetime


class TaskRequest(BaseModel):
    user_task: str = Field(
        min_length=5,
        max_length=5000,
        description="Task submitted by the user",
    )

    @field_validator("user_task")
    @classmethod
    def validate_user_task(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Task cannot be empty or whitespace only.")

        if len(value) < 5:
            raise ValueError("Task must contain at least 5 characters.")

        return value


class TaskResponse(BaseModel):
    task_id: str
    user_task: str
    execution_status: Literal[
        "planning", "executing", "reviewing",
        "completed", "failed"
    ]
    execution_plan: list[str] = []
    review_status: str
    retry_count: int
    final_output: str
    created_at: datetime | None = None
    email_source: bool = False
    email_sender: str | None = None
    email_subject: str | None = None
    email_record_id: int | None = None
    reply_status: str | None = None
    pending_reply: str | None = None


class TaskListItem(BaseModel):
    task_id: str
    user_task: str
    execution_status: str
    review_status: str
    retry_count: int
    created_at: datetime
    email_source: bool = False
    email_sender: str | None = None
    email_subject: str | None = None
    email_record_id: int | None = None
    reply_status: str | None = None


class TaskActivityResponse(BaseModel):
    id: int
    task_id: str
    agent_name: str
    activity_type: str
    status: str
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
