from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.models.conversation import Conversation
from app.models.task import Task


def make_conversation():
    conversation = MagicMock(spec=Conversation)
    conversation.id = uuid4()
    return conversation


def test_create_task_with_valid_conversation():
    db = MagicMock()
    conversation = make_conversation()

    (
        db.query.return_value
        .filter.return_value
        .first.return_value
    ) = conversation

    with (
        patch("app.api.tasks.SessionLocal", return_value=db),
        patch("app.api.tasks.execute_task_in_background"),
    ):
        response = TestClient(app).post(
            "/tasks/",
            json={
                "user_task": "Research AI workforce tools",
                "conversation_id": str(conversation.id),
            },
        )

    assert response.status_code == 202

    created_task = db.add.call_args.args[0]
    assert isinstance(created_task, Task)
    assert created_task.conversation_id == conversation.id

    db.commit.assert_called_once()
    db.close.assert_called_once()


def test_create_task_with_missing_conversation_returns_404():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    with (
        patch("app.api.tasks.SessionLocal", return_value=db),
        patch("app.api.tasks.execute_task_in_background"),
    ):
        response = TestClient(app).post(
            "/tasks/",
            json={
                "user_task": "Research AI workforce tools",
                "conversation_id": str(uuid4()),
            },
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found"

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.close.assert_called_once()


def test_create_task_without_conversation_remains_supported():
    db = MagicMock()

    with (
        patch("app.api.tasks.SessionLocal", return_value=db),
        patch("app.api.tasks.execute_task_in_background"),
    ):
        response = TestClient(app).post(
            "/tasks/",
            json={
                "user_task": "Research AI workforce tools",
            },
        )

    assert response.status_code == 202

    created_task = db.add.call_args.args[0]
    assert isinstance(created_task, Task)
    assert created_task.conversation_id is None

    db.query.assert_not_called()
    db.commit.assert_called_once()
    db.close.assert_called_once()
