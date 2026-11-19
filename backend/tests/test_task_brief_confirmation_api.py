
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.models.conversation import Conversation
from app.models.task import Task
from app.models.task_brief import TaskBrief


def make_brief():
    brief = MagicMock(spec=TaskBrief)
    brief.id = uuid4()
    brief.conversation_id = uuid4()
    brief.version = 1
    brief.objective = "Research AI workforce automation tools"
    brief.requirements = ["Compare available tools"]
    brief.constraints = ["Use reliable sources"]
    brief.expected_output = "A comparison report"
    brief.missing_information = []
    brief.status = "draft"
    brief.confirmed_at = None
    brief.created_at = datetime.now(timezone.utc)
    brief.updated_at = datetime.now(timezone.utc)
    return brief


def make_conversation(conversation_id):
    conversation = MagicMock(spec=Conversation)
    conversation.id = conversation_id
    return conversation


def configure_confirmation_queries(db, brief, existing_task=None, conversation=None):
    brief_query = MagicMock()
    task_query = MagicMock()
    conversation_query = MagicMock()

    db.query.side_effect = [
        brief_query,
        task_query,
        conversation_query,
    ]

    (
        brief_query
        .filter.return_value
        .with_for_update.return_value
        .first.return_value
    ) = brief

    task_query.filter.return_value.first.return_value = existing_task

    conversation_query.filter.return_value.first.return_value = conversation


def test_confirm_draft_brief_creates_and_schedules_task():
    db = MagicMock()
    brief = make_brief()
    conversation = make_conversation(brief.conversation_id)

    configure_confirmation_queries(
        db,
        brief,
        existing_task=None,
        conversation=conversation,
    )

    with (
        patch("app.api.tasks.SessionLocal", return_value=db),
        patch("app.api.tasks.execute_task_in_background") as execute_task,
    ):
        response = TestClient(app).post(
            f"/tasks/confirm-brief/{brief.id}",
        )

    assert response.status_code == 201

    body = response.json()

    assert body["task_brief"]["status"] == "confirmed"
    assert body["task_brief"]["id"] == str(brief.id)

    assert body["task"]["user_task"] == brief.objective
    assert body["task"]["execution_status"] == "planning"
    assert body["task"]["review_status"] == "pending"

    created_task = next(
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], Task)
    )

    assert created_task.task_brief_id == brief.id
    assert created_task.conversation_id == brief.conversation_id

    db.flush.assert_called_once()
    db.commit.assert_called_once()
    db.close.assert_called_once()

    execute_task.assert_called_once_with(
        created_task.task_id,
        brief.objective,
    )


def test_confirm_brief_returns_existing_task_without_creating_duplicate():
    db = MagicMock()
    brief = make_brief()

    existing_task = MagicMock(spec=Task)
    existing_task.task_id = str(uuid4())
    existing_task.user_task = brief.objective
    existing_task.execution_status = "completed"
    existing_task.execution_plan = ["Research"]
    existing_task.review_status = "approved"
    existing_task.retry_count = 0
    existing_task.final_output = "Completed report"
    existing_task.created_at = datetime.now(timezone.utc)

    configure_confirmation_queries(
        db,
        brief,
        existing_task=existing_task,
    )

    with (
        patch("app.api.tasks.SessionLocal", return_value=db),
        patch("app.api.tasks.execute_task_in_background") as execute_task,
    ):
        response = TestClient(app).post(
            f"/tasks/confirm-brief/{brief.id}",
        )

    assert response.status_code == 200
    assert response.json()["task"]["task_id"] == existing_task.task_id

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.close.assert_called_once()
    execute_task.assert_not_called()


def test_confirm_missing_brief_returns_404():
    db = MagicMock()

    brief_query = MagicMock()
    db.query.return_value = brief_query

    (
        brief_query
        .filter.return_value
        .with_for_update.return_value
        .first.return_value
    ) = None

    with patch("app.api.tasks.SessionLocal", return_value=db):
        response = TestClient(app).post(
            f"/tasks/confirm-brief/{uuid4()}",
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Task brief not found."

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.close.assert_called_once()


def test_confirm_brief_with_missing_information_returns_409():
    db = MagicMock()
    brief = make_brief()
    brief.missing_information = ["Target audience"]

    configure_confirmation_queries(
        db,
        brief,
        existing_task=None,
    )

    with patch("app.api.tasks.SessionLocal", return_value=db):
        response = TestClient(app).post(
            f"/tasks/confirm-brief/{brief.id}",
        )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Task brief still has missing information."
    )

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.close.assert_called_once()


def test_confirm_non_draft_brief_returns_409():
    db = MagicMock()
    brief = make_brief()
    brief.status = "confirmed"

    configure_confirmation_queries(
        db,
        brief,
        existing_task=None,
    )

    with patch("app.api.tasks.SessionLocal", return_value=db):
        response = TestClient(app).post(
            f"/tasks/confirm-brief/{brief.id}",
        )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Only draft task briefs can be confirmed."
    )

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.close.assert_called_once()


def test_confirm_brief_with_missing_conversation_returns_404():
    db = MagicMock()
    brief = make_brief()

    configure_confirmation_queries(
        db,
        brief,
        existing_task=None,
        conversation=None,
    )

    with patch("app.api.tasks.SessionLocal", return_value=db):
        response = TestClient(app).post(
            f"/tasks/confirm-brief/{brief.id}",
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found."

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.close.assert_called_once()


def test_confirm_brief_with_invalid_objective_returns_422():
    db = MagicMock()
    brief = make_brief()
    brief.objective = "Bad"

    conversation = make_conversation(brief.conversation_id)

    configure_confirmation_queries(
        db,
        brief,
        existing_task=None,
        conversation=conversation,
    )

    with patch("app.api.tasks.SessionLocal", return_value=db):
        response = TestClient(app).post(
            f"/tasks/confirm-brief/{brief.id}",
        )

    assert response.status_code == 422
    assert "between 5 and 5000 characters" in response.json()["detail"]

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.close.assert_called_once()


def test_confirm_brief_with_invalid_uuid_returns_422():
    with patch("app.api.tasks.SessionLocal") as session_local:
        response = TestClient(app).post(
            "/tasks/confirm-brief/not-a-valid-uuid",
        )

    assert response.status_code == 422
    session_local.assert_not_called()
