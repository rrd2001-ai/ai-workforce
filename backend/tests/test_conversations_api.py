from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database.db import get_db
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage


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


def test_create_conversation(client, db):
    def refresh_defaults(record):
        record.created_at = datetime.now(timezone.utc)
        record.updated_at = record.created_at

    db.refresh.side_effect = refresh_defaults

    response = client.post(
        "/conversations/",
        json={"title": "Test conversation"},
    )

    assert response.status_code == 201
    assert response.json()["title"] == "Test conversation"
    assert response.json()["status"] == "active"
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_create_conversation_without_title(client, db):
    def refresh_defaults(record):
        record.created_at = datetime.now(timezone.utc)
        record.updated_at = record.created_at

    db.refresh.side_effect = refresh_defaults

    response = client.post("/conversations/", json={})

    assert response.status_code == 201
    assert response.json()["title"] is None


def test_list_conversations(client, db):
    conversation = make_conversation()

    (
        db.query.return_value
        .order_by.return_value
        .offset.return_value
        .limit.return_value
        .all.return_value
    ) = [conversation]

    response = client.get("/conversations/")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == str(conversation.id)


def test_get_existing_conversation(client, db):
    conversation = make_conversation()
    db.query.return_value.filter.return_value.first.return_value = conversation

    response = client.get(f"/conversations/{conversation.id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(conversation.id)


def test_get_missing_conversation_returns_404(client, db):
    db.query.return_value.filter.return_value.first.return_value = None

    response = client.get(f"/conversations/{uuid4()}")

    assert response.status_code == 404


def test_add_conversation_message(client, db):
    conversation = make_conversation()
    db.query.return_value.filter.return_value.first.return_value = conversation

    def flush_defaults():
        for record in db.add.call_args_list:
            message = record.args[0]
            if isinstance(message, ConversationMessage):
                message.created_at = datetime.now(timezone.utc)

    db.flush.side_effect = flush_defaults

    response = client.post(
        f"/conversations/{conversation.id}/messages",
        json={
            "role": "user",
            "content": "Hello AI Workforce",
            "metadata": {"source": "test"},
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "user"
    assert response.json()["content"] == "Hello AI Workforce"
    assert response.json()["metadata"] == {"source": "test"}
    db.commit.assert_called_once()


def test_add_message_to_missing_conversation_returns_404(client, db):
    db.query.return_value.filter.return_value.first.return_value = None

    response = client.post(
        f"/conversations/{uuid4()}/messages",
        json={
            "role": "user",
            "content": "Hello",
        },
    )

    assert response.status_code == 404


def test_invalid_message_role_is_rejected(client, db):
    conversation = make_conversation()
    db.query.return_value.filter.return_value.first.return_value = conversation

    response = client.post(
        f"/conversations/{conversation.id}/messages",
        json={
            "role": "worker",
            "content": "Hello",
        },
    )

    assert response.status_code == 422
    db.add.assert_not_called()


def test_message_content_cannot_be_empty(client, db):
    conversation = make_conversation()
    db.query.return_value.filter.return_value.first.return_value = conversation

    response = client.post(
        f"/conversations/{conversation.id}/messages",
        json={
            "role": "user",
            "content": "   ",
        },
    )

    assert response.status_code == 422


def test_list_messages_for_conversation(client, db):
    conversation = make_conversation()

    message = ConversationMessage(
        id=uuid4(),
        conversation_id=conversation.id,
        role="user",
        content="Hello",
        message_type="chat",
        message_metadata={"source": "test"},
        created_at=datetime.now(timezone.utc),
    )

    conversation_query = MagicMock()
    conversation_query.filter.return_value.first.return_value = (
        conversation.id,
    )

    message_query = MagicMock()
    (
        message_query.filter.return_value
        .order_by.return_value
        .offset.return_value
        .limit.return_value
        .all.return_value
    ) = [message]

    db.query.side_effect = [conversation_query, message_query]

    response = client.get(
        f"/conversations/{conversation.id}/messages"
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["content"] == "Hello"
    assert response.json()[0]["metadata"] == {"source": "test"}


def test_list_messages_for_missing_conversation_returns_404(client, db):
    db.query.return_value.filter.return_value.first.return_value = None

    response = client.get(
        f"/conversations/{uuid4()}/messages"
    )

    assert response.status_code == 404


def test_conversation_list_pagination_limits(client, db):
    response = client.get("/conversations/?limit=101")

    assert response.status_code == 422

    response = client.get("/conversations/?limit=0")

    assert response.status_code == 422
