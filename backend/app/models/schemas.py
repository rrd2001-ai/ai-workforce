
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal
from datetime import datetime


class TaskRequest(BaseModel):
    user_task: str = Field(
        min_length=5,
        description="Task submitted by the user"
    )


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

class TaskListItem(BaseModel):
    task_id: str
    user_task: str
    execution_status: str
    review_status: str
    retry_count: int
    created_at: datetime


class TaskActivityResponse(BaseModel):
    id: int
    task_id: str
    agent_name: str
    activity_type: str
    status: str
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
