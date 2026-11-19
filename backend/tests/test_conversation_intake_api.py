
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database.db import get_db
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.task_brief import TaskBrief


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    yield TestClient(app)

    app.dependency_overrides.clear()


def make_conversation():
    now = datetime.now(timezone.utc)

    return Conversation(
        id=uuid4(),
        title="Test conversation",
        status="active",
        created_at=now,
        updated_at=now,
    )


def make_brief(conversation_id, version=1):
    now = datetime.now(timezone.utc)

    return TaskBrief(
        id=uuid4(),
        conversation_id=conversation_id,
        version=version,
        objective="Build a task management application",
        requirements=["User authentication"],
        constraints=[],
        expected_output="Working application",
        missing_information=[],
        status="draft",
        created_at=now,
        updated_at=now,
    )


def configure_intake_queries(db, conversation, current_brief=None):
    conversation_query = MagicMock()
    (
        conversation_query
        .filter.return_value
        .with_for_update.return_value
        .first.return_value
    ) = conversation

    brief_query = MagicMock()
    (
        brief_query
        .filter.return_value
        .order_by.return_value
        .first.return_value
    ) = current_brief

    db.query.side_effect = [
        conversation_query,
        brief_query,
    ]

    return conversation_query, brief_query


def configure_flush_defaults(db):
    def set_defaults():
        now = datetime.now(timezone.utc)

        for call in db.add.call_args_list:
            record = call.args[0]

            if isinstance(record, (ConversationMessage, TaskBrief)):
                if record.created_at is None:
                    record.created_at = now

            if isinstance(record, TaskBrief):
                if record.updated_at is None:
                    record.updated_at = now

    db.flush.side_effect = set_defaults


def test_intake_returns_404_for_missing_conversation(
    client,
    db,
):
    conversation_query = MagicMock()
    (
        conversation_query
        .filter.return_value
        .with_for_update.return_value
        .first.return_value
    ) = None

    db.query.return_value = conversation_query

    response = client.post(
        f"/conversations/{uuid4()}/intake",
        json={"message": "Build an application"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found."

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_intake_saves_clarification_exchange_without_creating_brief(
    client,
    db,
    monkeypatch,
):
    import app.api.conversations as conversations_api

    conversation = make_conversation()

    configure_intake_queries(db, conversation)

    monkeypatch.setattr(
        conversations_api,
        "retrieve_conversation_messages",
        lambda db, conversation_id: [],
    )

    monkeypatch.setattr(
        conversations_api,
        "analyze_intake",
        lambda **kwargs: {
            "status": "needs_clarification",
            "assistant_message": "Which programming language should be used?",
            "objective": "Build an application",
            "requirements": [],
            "constraints": [],
            "expected_output": None,
            "missing_information": ["Programming language"],
        },
    )

    configure_flush_defaults(db)

    response = client.post(
        f"/conversations/{conversation.id}/intake",
        json={"message": "Build an application"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "needs_clarification"
    assert data["assistant_message"] == (
        "Which programming language should be used?"
    )
    assert data["task_brief"] is None

    added_records = [
        call.args[0]
        for call in db.add.call_args_list
    ]

    assert len(added_records) == 2
    assert all(
        isinstance(record, ConversationMessage)
        for record in added_records
    )

    assert added_records[0].role == "user"
    assert added_records[1].role == "assistant"

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_intake_creates_first_draft_brief(
    client,
    db,
    monkeypatch,
):
    import app.api.conversations as conversations_api

    conversation = make_conversation()

    configure_intake_queries(db, conversation)

    monkeypatch.setattr(
        conversations_api,
        "retrieve_conversation_messages",
        lambda db, conversation_id: [],
    )

    monkeypatch.setattr(
        conversations_api,
        "analyze_intake",
        lambda **kwargs: {
            "status": "ready_for_review",
            "assistant_message": "Please review the proposed task.",
            "objective": "Build a task management application",
            "requirements": ["User authentication"],
            "constraints": ["Use Python"],
            "expected_output": "Working application",
            "missing_information": [],
        },
    )

    configure_flush_defaults(db)

    response = client.post(
        f"/conversations/{conversation.id}/intake",
        json={"message": "Build a task management application"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ready_for_review"
    assert data["task_brief"] is not None
    assert data["task_brief"]["version"] == 1
    assert data["task_brief"]["status"] == "draft"
    assert data["task_brief"]["objective"] == (
        "Build a task management application"
    )

    added_records = [
        call.args[0]
        for call in db.add.call_args_list
    ]

    messages = [
        record
        for record in added_records
        if isinstance(record, ConversationMessage)
    ]

    briefs = [
        record
        for record in added_records
        if isinstance(record, TaskBrief)
    ]

    assert len(messages) == 2
    assert len(briefs) == 1
    assert briefs[0].version == 1

    # Intake must not create an executable task.
    assert len(added_records) == 3

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_intake_increments_existing_brief_version(
    client,
    db,
    monkeypatch,
):
    import app.api.conversations as conversations_api

    conversation = make_conversation()
    existing_brief = make_brief(conversation.id, version=2)

    configure_intake_queries(
        db,
        conversation,
        existing_brief,
    )

    monkeypatch.setattr(
        conversations_api,
        "retrieve_conversation_messages",
        lambda db, conversation_id: [],
    )

    monkeypatch.setattr(
        conversations_api,
        "analyze_intake",
        lambda **kwargs: {
            "status": "ready_for_review",
            "assistant_message": "Please review the updated task.",
            "objective": "Build an updated application",
            "requirements": ["Authentication", "Dashboard"],
            "constraints": [],
            "expected_output": "Working application",
            "missing_information": [],
        },
    )

    configure_flush_defaults(db)

    response = client.post(
        f"/conversations/{conversation.id}/intake",
        json={"message": "Add a dashboard"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["task_brief"]["version"] == 3
    assert data["task_brief"]["objective"] == (
        "Build an updated application"
    )

    created_briefs = [
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], TaskBrief)
    ]

    assert len(created_briefs) == 1
    assert created_briefs[0].version == 3

    # The existing version must remain unchanged.
    assert existing_brief.version == 2

    db.commit.assert_called_once()


def test_intake_rolls_back_when_master_response_is_invalid(
    client,
    db,
    monkeypatch,
):
    import app.api.conversations as conversations_api

    conversation = make_conversation()

    configure_intake_queries(db, conversation)

    monkeypatch.setattr(
        conversations_api,
        "retrieve_conversation_messages",
        lambda db, conversation_id: [],
    )

    def raise_invalid_response(**kwargs):
        raise ValueError("Invalid Master response")

    monkeypatch.setattr(
        conversations_api,
        "analyze_intake",
        raise_invalid_response,
    )

    response = client.post(
        f"/conversations/{conversation.id}/intake",
        json={"message": "Build an application"},
    )

    assert response.status_code == 502

    assert response.json()["detail"] == (
        "Master could not process the request. Please try again."
    )

    db.rollback.assert_called_once()
    db.commit.assert_called_once()


def test_intake_rejects_whitespace_message(
    client,
    db,
):
    response = client.post(
        f"/conversations/{uuid4()}/intake",
        json={"message": "   "},
    )

    assert response.status_code == 422
    db.query.assert_not_called()


def test_intake_rejects_message_over_maximum_length(
    client,
    db,
):
    response = client.post(
        f"/conversations/{uuid4()}/intake",
        json={"message": "a" * 10_001},
    )

    assert response.status_code == 422
    db.query.assert_not_called()
