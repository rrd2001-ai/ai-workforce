import logging

from app.agents.manager import manager_plan, manager_review
from app.agents.worker import worker_execute
from app.services.activity_logger import log_activity

logger = logging.getLogger(__name__)


def record_activity(state, agent_name, activity_type, status, message):
    try:
        task_id = state.get("task_id")
        if task_id:
            log_activity(
                task_id=task_id,
                agent_name=agent_name,
                activity_type=activity_type,
                status=status,
                message=message,
            )
    except Exception:
        logger.exception("Could not record task activity")


def manager_plan_node(state: dict) -> dict:
    record_activity(
        state, "Manager Agent", "planning", "started",
        "Manager started analyzing the task."
    )
    try:
        result = manager_plan(state)
        record_activity(
            state, "Manager Agent", "planning", "completed",
            "Manager generated the execution plan."
        )
        return result
    except Exception:
        record_activity(
            state, "Manager Agent", "planning", "failed",
            "Manager encountered an error during planning."
        )
        raise


def worker_execute_node(state: dict) -> dict:
    record_activity(
        state, "Worker Agent", "execution", "started",
        "Worker started executing the assigned task."
    )
    try:
        result = worker_execute(state)
        record_activity(
            state, "Worker Agent", "execution", "completed",
            "Worker generated the requested output."
        )
        return result
    except Exception:
        record_activity(
            state, "Worker Agent", "execution", "failed",
            "Worker encountered an execution error."
        )
        raise


def manager_review_node(state: dict) -> dict:
    record_activity(
        state, "Manager Agent", "review", "started",
        "Manager started reviewing the Worker output."
    )
    try:
        result = manager_review(state)
        review_status = result.get("review_status", "pending")

        if review_status == "approved":
            message = "Manager approved the Worker output."
        else:
            message = (
                "Manager rejected the Worker output. Feedback: "
                + result.get("review_feedback", "No feedback provided.")
            )

        record_activity(
            state, "Manager Agent", "review", review_status, message
        )
        return result
    except Exception:
        record_activity(
            state, "Manager Agent", "review", "failed",
            "Manager encountered an error during review."
        )
        raise


def retry_check_node(state: dict) -> dict:
    retry_count = state.get("retry_count", 0) + 1

    record_activity(
        state, "Manager Agent", "retry", "started",
        f"Manager initiated retry attempt {retry_count}."
    )

    return {
        "retry_count": retry_count,
        "execution_status": (
            "executing" if retry_count <= 2 else "failed"
        ),
    }


def finalize_result_node(state: dict) -> dict:
    record_activity(
        state, "System", "finalization", "completed",
        "Task approved and final output prepared."
    )

    return {
        "final_output": state.get("worker_output", ""),
        "review_status": "approved",
        "execution_status": "completed",
    }


def fail_task_node(state: dict) -> dict:
    message = (
        "Task could not be completed after the maximum of 2 retries. "
        "Last review feedback: "
        + state.get("review_feedback", "")
    )

    record_activity(
        state, "System", "finalization", "failed", message
    )

    return {
        "final_output": message,
        "execution_status": "failed",
    }
