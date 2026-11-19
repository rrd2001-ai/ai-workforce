from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Literal
from datetime import datetime
from uuid import UUID


class TaskRequest(BaseModel):
    user_task: str = Field(
        min_length=5,
        max_length=5000,
        description="Task submitted by the user",
    )
    conversation_id: UUID | None = None

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


# Conversation schemas

class ConversationCreate(BaseModel):
    title: str | None = Field(
        default=None,
        max_length=200,
    )


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ConversationMessageCreate(BaseModel):
    role: str = Field(
        min_length=1,
        max_length=20,
    )
    content: str = Field(
        min_length=1,
        max_length=50000,
    )
    message_type: str = Field(
        default="chat",
        min_length=1,
        max_length=30,
    )
    metadata: dict | None = None

    @field_validator("role", "message_type")
    @classmethod
    def validate_nonempty_fields(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be empty or whitespace only.")
        return value

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message content cannot be empty.")
        return value


class ConversationMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    message_type: str
    metadata: dict | None = Field(
        default=None,
        validation_alias="message_metadata",
    )
    created_at: datetime


class ConversationIntakeRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=10_000,
        description="User's task description or clarification",
    )

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Message cannot be empty or whitespace only.")

        return value


class TaskBriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    version: int
    objective: str
    requirements: list[str]
    constraints: list[str]
    expected_output: str | None
    missing_information: list[str]
    status: str
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime

class TaskBriefConfirmationResponse(BaseModel):
    task_brief: TaskBriefResponse
    task: TaskResponse

class ConversationIntakeResponse(BaseModel):
    status: Literal["needs_clarification", "ready_for_review"]
    assistant_message: str
    task_brief: TaskBriefResponse | None = None

