
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import MagicMock

from app.models.user_memory import UserMemory
from app.services.history_retrieval import (
    retrieve_conversation_messages,
    retrieve_conversation_tasks,
    retrieve_task_activities,
    retrieve_history_context,
    retrieve_user_memories,
    retrieve_task_inventory,
)


def make_message(role, content, message_id=None):
    return SimpleNamespace(
        id=message_id or uuid4(),
        role=role,
        content=content,
        message_type="chat",
        created_at=datetime.now(timezone.utc),
    )


def make_task(task_id):
    return SimpleNamespace(
        task_id=task_id,
        user_task=f"Task {task_id}",
        execution_status="completed",
        review_status="approved",
        final_output="Task result",
        review_feedback=None,
        created_at=datetime.now(timezone.utc),
    )


def make_activity(task_id, activity_id):
    return SimpleNamespace(
        task_id=task_id,
        agent_name="Manager Agent",
        activity_type="planning",
        status="completed",
        message="Planning completed",
        created_at=datetime.now(timezone.utc),
        id=activity_id,
    )


def make_memory(
    memory_key,
    memory_value,
    importance=5,
    memory_type="preference",
):
    return SimpleNamespace(
        memory_key=memory_key,
        memory_value=memory_value,
        memory_type=memory_type,
        importance=importance,
        updated_at=datetime.now(timezone.utc),
    )


def test_retrieve_conversation_messages_returns_chronological_order():
    db = MagicMock()
    conversation_id = uuid4()

    older = make_message("user", "First message")
    newer = make_message("assistant", "Second message")

    (
        db.query.return_value
        .filter.return_value
        .order_by.return_value
        .limit.return_value
        .all.return_value
    ) = [newer, older]

    result = retrieve_conversation_messages(db, conversation_id)

    assert len(result) == 2
    assert result[0]["content"] == "First message"
    assert result[1]["content"] == "Second message"
    assert result[0]["role"] == "user"


def test_retrieve_conversation_messages_applies_limit():
    db = MagicMock()

    (
        db.query.return_value
        .filter.return_value
        .order_by.return_value
        .limit.return_value
        .all.return_value
    ) = []

    retrieve_conversation_messages(
        db,
        uuid4(),
        limit=5,
    )

    db.query.return_value.filter.return_value.order_by.return_value.limit.assert_called_once_with(5)


def test_retrieve_conversation_tasks_returns_task_details():
    db = MagicMock()
    conversation_id = uuid4()
    task = make_task("task-123")

    (
        db.query.return_value
        .filter.return_value
        .order_by.return_value
        .limit.return_value
        .all.return_value
    ) = [task]

    result = retrieve_conversation_tasks(db, conversation_id)

    assert len(result) == 1
    assert result[0]["task_id"] == "task-123"
    assert result[0]["user_task"] == "Task task-123"
    assert result[0]["execution_status"] == "completed"
    assert result[0]["final_output"] == "Task result"


def test_retrieve_task_activities_returns_chronological_order():
    db = MagicMock()
    task_id = "task-123"

    older = make_activity(task_id, 1)
    newer = make_activity(task_id, 2)

    (
        db.query.return_value
        .filter.return_value
        .order_by.return_value
        .limit.return_value
        .all.return_value
    ) = [newer, older]

    result = retrieve_task_activities(db, [task_id])

    assert len(result[task_id]) == 2
    assert result[task_id][0]["message"] == "Planning completed"
    db.query.assert_called_once()


def test_retrieve_task_activities_returns_empty_for_no_task_ids():
    db = MagicMock()

    result = retrieve_task_activities(db, [])

    assert result == {}
    db.query.assert_not_called()


def test_retrieve_history_context_combines_all_history():
    db = MagicMock()
    conversation_id = uuid4()

    message = make_message("user", "Please prepare a report.")
    task = make_task("task-456")
    activity = make_activity("task-456", 1)

    message_query = MagicMock()
    message_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        message
    ]

    task_query = MagicMock()
    task_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        task
    ]

    activity_query = MagicMock()
    activity_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        activity
    ]

    memory_query = MagicMock()
    memory_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

    count_query = MagicMock()
    count_query.filter.return_value = count_query
    count_query.scalar.return_value = 1

    inventory_query = MagicMock()
    inventory_query.filter.return_value = inventory_query
    inventory_query.order_by.return_value.limit.return_value.offset.return_value.all.return_value = [
        task
    ]

    db.query.side_effect = [
        message_query,
        task_query,
        activity_query,
        memory_query,
        count_query,
        inventory_query,
    ]

    result = retrieve_history_context(db, conversation_id)

    assert result["conversation_id"] == str(conversation_id)
    assert len(result["messages"]) == 1
    assert len(result["tasks"]) == 1
    assert result["task_activities"]["task-456"][0]["agent_name"] == "Manager Agent"
    assert result["memories"] == []

    assert result["task_inventory"]["total_count"] == 1
    assert result["task_inventory"]["returned_count"] == 1
    assert result["task_inventory"]["has_more"] is False
    assert result["task_inventory"]["tasks"][0]["task_id"] == "task-456"

    assert db.query.call_count == 6


def test_retrieve_history_context_handles_empty_conversation():
    db = MagicMock()
    conversation_id = uuid4()

    message_query = MagicMock()
    message_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

    task_query = MagicMock()
    task_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

    memory_query = MagicMock()
    memory_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

    count_query = MagicMock()
    count_query.filter.return_value = count_query
    count_query.scalar.return_value = 0

    inventory_query = MagicMock()
    inventory_query.filter.return_value = inventory_query
    inventory_query.order_by.return_value.limit.return_value.offset.return_value.all.return_value = []

    db.query.side_effect = [
        message_query,
        task_query,
        memory_query,
        count_query,
        inventory_query,
    ]

    result = retrieve_history_context(db, conversation_id)

    assert result["messages"] == []
    assert result["tasks"] == []
    assert result["task_activities"] == {}
    assert result["memories"] == []

    assert result["task_inventory"]["total_count"] == 0
    assert result["task_inventory"]["tasks"] == []
    assert result["task_inventory"]["has_more"] is False

    assert db.query.call_count == 5


def test_retrieve_conversation_tasks_excludes_current_task():
    db = MagicMock()
    conversation_id = uuid4()
    previous_task = make_task("task-previous")

    query = db.query.return_value
    query.filter.return_value = query
    (
        query.order_by.return_value
        .limit.return_value
        .all.return_value
    ) = [previous_task]

    result = retrieve_conversation_tasks(
        db,
        conversation_id,
        exclude_task_id="task-current",
    )

    assert len(result) == 1
    assert result[0]["task_id"] == "task-previous"
    assert query.filter.call_count == 2

    exclusion_filter = query.filter.call_args_list[1].args[0]
    assert exclusion_filter.right.value == "task-current"


def test_retrieve_user_memories_returns_serialized_memory_fields():
    db = MagicMock()
    memory = make_memory(
        "response_style",
        "Prefer concise answers.",
        importance=9,
    )

    (
        db.query.return_value
        .filter.return_value
        .filter.return_value
        .order_by.return_value
        .limit.return_value
        .all.return_value
    ) = [memory]

    result = retrieve_user_memories(db, uuid4())

    assert len(result) == 1
    assert result[0]["memory_key"] == "response_style"
    assert result[0]["memory_value"] == "Prefer concise answers."
    assert result[0]["memory_type"] == "preference"
    assert result[0]["importance"] == 9
    assert isinstance(result[0]["updated_at"], str)


def test_retrieve_user_memories_filters_active_and_hybrid_scope():
    db = MagicMock()
    conversation_id = uuid4()
    query = db.query.return_value
    query.filter.return_value = query
    query.order_by.return_value.limit.return_value.all.return_value = []

    retrieve_user_memories(db, conversation_id)

    assert db.query.call_args.args == (UserMemory,)
    assert query.filter.call_count == 2

    active_filter = query.filter.call_args_list[0].args[0]
    assert "is_active" in str(active_filter)

    scope_filter = query.filter.call_args_list[1].args[0]
    scope_sql = str(scope_filter)
    assert "source_conversation_id IS NULL" in scope_sql
    assert "source_conversation_id =" in scope_sql


def test_retrieve_user_memories_without_conversation_returns_global_only():
    db = MagicMock()
    query = db.query.return_value
    query.filter.return_value = query
    query.order_by.return_value.limit.return_value.all.return_value = []

    retrieve_user_memories(db, conversation_id=None)

    assert query.filter.call_count == 2

    scope_filter = query.filter.call_args_list[1].args[0]
    assert "source_conversation_id" in str(scope_filter)
    assert "IS NULL" in str(scope_filter).upper()


def test_retrieve_user_memories_applies_priority_ordering_and_default_limit():
    db = MagicMock()
    query = db.query.return_value
    query.filter.return_value = query
    query.order_by.return_value.limit.return_value.all.return_value = []

    retrieve_user_memories(db, uuid4())

    query.order_by.assert_called_once()
    assert len(query.order_by.call_args.args) == 3
    query.order_by.return_value.limit.assert_called_once_with(30)


def test_retrieve_user_memories_supports_custom_limit():
    db = MagicMock()
    query = db.query.return_value
    query.filter.return_value = query
    query.order_by.return_value.limit.return_value.all.return_value = []

    retrieve_user_memories(db, uuid4(), limit=7)

    query.order_by.return_value.limit.assert_called_once_with(7)


def test_retrieve_history_context_without_conversation_returns_global_memories():
    db = MagicMock()

    memory = make_memory(
        "work_style",
        "Use Python where appropriate.",
    )

    task_query = MagicMock()
    task_query.filter.return_value = task_query
    task_query.order_by.return_value.limit.return_value.all.return_value = []

    memory_query = MagicMock()
    memory_query.filter.return_value = memory_query
    memory_query.order_by.return_value.limit.return_value.all.return_value = [
        memory
    ]

    count_query = MagicMock()
    count_query.scalar.return_value = 0

    inventory_query = MagicMock()
    inventory_query.order_by.return_value.limit.return_value.offset.return_value.all.return_value = []

    db.query.side_effect = [
        task_query,
        memory_query,
        count_query,
        inventory_query,
    ]

    result = retrieve_history_context(db, None)

    assert result["conversation_id"] is None
    assert result["messages"] == []
    assert result["tasks"] == []
    assert result["task_activities"] == {}
    assert result["memories"][0]["memory_key"] == "work_style"

    assert result["task_inventory"]["total_count"] == 0
    assert result["task_inventory"]["tasks"] == []

    assert db.query.call_count == 4
    assert db.query.call_args_list[0].args[0].__name__ == "Task"
    assert db.query.call_args_list[1].args == (UserMemory,)


def test_retrieve_history_context_without_conversation_includes_recent_tasks():
    db = MagicMock()

    previous_task = make_task("task-previous")

    task_query = MagicMock()
    task_query.filter.return_value = task_query
    task_query.order_by.return_value.limit.return_value.all.return_value = [
        previous_task
    ]

    activity_query = MagicMock()
    activity_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

    memory_query = MagicMock()
    memory_query.filter.return_value = memory_query
    memory_query.order_by.return_value.limit.return_value.all.return_value = []

    count_query = MagicMock()
    count_query.filter.return_value = count_query
    count_query.scalar.return_value = 1

    inventory_query = MagicMock()
    inventory_query.filter.return_value = inventory_query
    inventory_query.order_by.return_value.limit.return_value.offset.return_value.all.return_value = [
        previous_task
    ]

    db.query.side_effect = [
        task_query,
        activity_query,
        memory_query,
        count_query,
        inventory_query,
    ]

    result = retrieve_history_context(
        db,
        conversation_id=None,
        exclude_task_id="task-current",
    )

    assert result["conversation_id"] is None
    assert result["messages"] == []
    assert len(result["tasks"]) == 1
    assert result["tasks"][0]["task_id"] == "task-previous"
    assert result["task_activities"] == {"task-previous": []}
    assert result["memories"] == []

    assert result["task_inventory"]["total_count"] == 1
    assert result["task_inventory"]["returned_count"] == 1
    assert result["task_inventory"]["tasks"][0]["task_id"] == "task-previous"

    exclusion_filter = task_query.filter.call_args.args[0]
    assert exclusion_filter.right.value == "task-current"


def test_retrieve_task_inventory_returns_compact_records():
    db = MagicMock()

    first_task = make_task("task-1")
    second_task = make_task("task-2")

    count_query = MagicMock()
    count_query.scalar.return_value = 2

    inventory_query = MagicMock()
    (
        inventory_query
        .order_by.return_value
        .limit.return_value
        .offset.return_value
        .all.return_value
    ) = [first_task, second_task]

    db.query.side_effect = [count_query, inventory_query]

    result = retrieve_task_inventory(db)

    assert result["total_count"] == 2
    assert result["returned_count"] == 2
    assert result["has_more"] is False
    assert len(result["tasks"]) == 2

    task = result["tasks"][0]

    assert task["task_id"] == "task-1"
    assert task["user_task"] == "Task task-1"
    assert task["execution_status"] == "completed"
    assert task["review_status"] == "approved"
    assert isinstance(task["created_at"], str)

    assert "final_output" not in task
    assert "review_feedback" not in task


def test_retrieve_task_inventory_reports_incomplete_results():
    db = MagicMock()

    task = make_task("task-1")

    count_query = MagicMock()
    count_query.scalar.return_value = 150

    inventory_query = MagicMock()
    (
        inventory_query
        .order_by.return_value
        .limit.return_value
        .offset.return_value
        .all.return_value
    ) = [task]

    db.query.side_effect = [count_query, inventory_query]

    result = retrieve_task_inventory(db, limit=1)

    assert result["total_count"] == 150
    assert result["returned_count"] == 1
    assert result["has_more"] is True
