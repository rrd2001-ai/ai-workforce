
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.conversation_message import ConversationMessage
from app.models.task import Task
from app.models.task_activity import TaskActivity
from app.models.user_memory import UserMemory


DEFAULT_MESSAGE_LIMIT = 20
DEFAULT_TASK_LIMIT = 10
DEFAULT_ACTIVITIES_PER_TASK = 5
DEFAULT_MEMORY_LIMIT = 30
DEFAULT_TASK_INVENTORY_LIMIT = 100


def retrieve_conversation_messages(
    db: Session,
    conversation_id: UUID,
    limit: int = DEFAULT_MESSAGE_LIMIT,
) -> list[dict]:
    messages = (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.conversation_id == conversation_id
        )
        .order_by(
            ConversationMessage.created_at.desc(),
            ConversationMessage.id.desc(),
        )
        .limit(limit)
        .all()
    )

    messages.reverse()

    return [
        {
            "role": message.role,
            "content": message.content,
            "message_type": message.message_type,
            "created_at": message.created_at.isoformat(),
        }
        for message in messages
    ]


def retrieve_conversation_tasks(
    db: Session,
    conversation_id: UUID,
    limit: int = DEFAULT_TASK_LIMIT,
    exclude_task_id: str | None = None,
) -> list[dict]:
    query = db.query(Task).filter(
        Task.conversation_id == conversation_id
    )

    if exclude_task_id is not None:
        query = query.filter(Task.task_id != exclude_task_id)

    tasks = (
        query
        .order_by(
            Task.created_at.desc(),
            Task.id.desc(),
        )
        .limit(limit)
        .all()
    )

    return [
        {
            "task_id": task.task_id,
            "user_task": task.user_task,
            "execution_status": task.execution_status,
            "review_status": task.review_status,
            "final_output": task.final_output,
            "review_feedback": task.review_feedback,
            "created_at": task.created_at.isoformat(),
        }
        for task in tasks
    ]


def retrieve_recent_tasks(
    db: Session,
    limit: int = DEFAULT_TASK_LIMIT,
    exclude_task_id: str | None = None,
) -> list[dict]:
    """Retrieve recent tasks across the workspace."""
    query = db.query(Task)

    if exclude_task_id is not None:
        query = query.filter(Task.task_id != exclude_task_id)

    tasks = (
        query
        .order_by(
            Task.created_at.desc(),
            Task.id.desc(),
        )
        .limit(limit)
        .all()
    )

    return [
        {
            "task_id": task.task_id,
            "user_task": task.user_task,
            "execution_status": task.execution_status,
            "review_status": task.review_status,
            "final_output": task.final_output,
            "review_feedback": task.review_feedback,
            "created_at": task.created_at.isoformat(),
        }
        for task in tasks
    ]


def retrieve_task_inventory(
    db: Session,
    conversation_id: UUID | None = None,
    exclude_task_id: str | None = None,
    limit: int = DEFAULT_TASK_INVENTORY_LIMIT,
    offset: int = 0,
) -> dict:
    """
    Retrieve a compact, paginated inventory of workspace or
    conversation tasks without loading task outputs.
    """
    if limit < 1:
        raise ValueError("limit must be greater than zero.")

    if offset < 0:
        raise ValueError("offset cannot be negative.")

    count_query = db.query(func.count(Task.id))
    inventory_query = db.query(Task)

    if conversation_id is not None:
        count_query = count_query.filter(
            Task.conversation_id == conversation_id
        )
        inventory_query = inventory_query.filter(
            Task.conversation_id == conversation_id
        )

    if exclude_task_id is not None:
        count_query = count_query.filter(
            Task.task_id != exclude_task_id
        )
        inventory_query = inventory_query.filter(
            Task.task_id != exclude_task_id
        )

    total_count = count_query.scalar() or 0

    tasks = (
        inventory_query
        .order_by(
            Task.created_at.asc(),
            Task.id.asc(),
        )
        .limit(limit)
        .offset(offset)
        .all()
    )

    inventory = [
        {
            "task_id": task.task_id,
            "user_task": task.user_task,
            "execution_status": task.execution_status,
            "review_status": task.review_status,
            "created_at": task.created_at.isoformat(),
        }
        for task in tasks
    ]

    returned_count = len(inventory)

    return {
        "tasks": inventory,
        "total_count": total_count,
        "returned_count": returned_count,
        "offset": offset,
        "limit": limit,
        "has_more": offset + returned_count < total_count,
    }


def retrieve_task_activities(
    db: Session,
    task_ids: list[str],
    limit_per_task: int = DEFAULT_ACTIVITIES_PER_TASK,
) -> dict[str, list[dict]]:
    activities_by_task: dict[str, list[dict]] = {}

    for task_id in task_ids:
        activities = (
            db.query(TaskActivity)
            .filter(TaskActivity.task_id == task_id)
            .order_by(
                TaskActivity.created_at.desc(),
                TaskActivity.id.desc(),
            )
            .limit(limit_per_task)
            .all()
        )

        activities.reverse()

        activities_by_task[task_id] = [
            {
                "agent_name": activity.agent_name,
                "activity_type": activity.activity_type,
                "status": activity.status,
                "message": activity.message,
                "created_at": activity.created_at.isoformat(),
            }
            for activity in activities
        ]

    return activities_by_task


def retrieve_user_memories(
    db: Session,
    conversation_id: UUID | None = None,
    limit: int = DEFAULT_MEMORY_LIMIT,
) -> list[dict]:
    query = db.query(UserMemory).filter(
        UserMemory.is_active.is_(True)
    )

    if conversation_id is None:
        query = query.filter(
            UserMemory.source_conversation_id.is_(None)
        )
    else:
        query = query.filter(
            or_(
                UserMemory.source_conversation_id.is_(None),
                UserMemory.source_conversation_id == conversation_id,
            )
        )

    memories = (
        query
        .order_by(
            UserMemory.importance.desc(),
            UserMemory.updated_at.desc(),
            UserMemory.id.desc(),
        )
        .limit(limit)
        .all()
    )

    return [
        {
            "memory_key": memory.memory_key,
            "memory_value": memory.memory_value,
            "memory_type": memory.memory_type,
            "importance": memory.importance,
            "updated_at": memory.updated_at.isoformat(),
        }
        for memory in memories
    ]


def retrieve_history_context(
    db: Session,
    conversation_id: UUID | None,
    exclude_task_id: str | None = None,
) -> dict:
    messages = []
    tasks = []

    if conversation_id is not None:
        messages = retrieve_conversation_messages(
            db,
            conversation_id,
        )

        tasks = retrieve_conversation_tasks(
            db,
            conversation_id,
            exclude_task_id=exclude_task_id,
        )
    else:
        tasks = retrieve_recent_tasks(
            db,
            exclude_task_id=exclude_task_id,
        )

    task_ids = [task["task_id"] for task in tasks]

    activities = retrieve_task_activities(
        db,
        task_ids,
    )

    memories = retrieve_user_memories(
        db,
        conversation_id=conversation_id,
    )

    task_inventory = retrieve_task_inventory(
        db,
        conversation_id=conversation_id,
        exclude_task_id=exclude_task_id,
    )

    return {
        "conversation_id": (
            str(conversation_id) if conversation_id is not None else None
        ),
        "messages": messages,
        "tasks": tasks,
        "task_activities": activities,
        "memories": memories,
        "task_inventory": task_inventory,
    }