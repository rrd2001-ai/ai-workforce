from typing import TypedDict, Literal


class WorkforceState(TypedDict, total=False):
    task_id: str
    user_task: str
    execution_plan: list[str]
    worker_assignment: str
    acceptance_criteria: str
    worker_output: str
    review_feedback: str
    review_status: Literal["pending", "approved", "rejected"]
    retry_count: int
    execution_status: Literal[
        "planning", "executing", "reviewing", "completed", "failed"
    ]
    final_output: str
