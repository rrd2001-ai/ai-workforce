from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.models.user_memory import UserMemory
from app.services.memory_service import (
    _validate_memory_fields,
    deactivate_user_memory,
    upsert_user_memory,
)


def test_validate_memory_fields_trims_values():
    result = _validate_memory_fields(
        "  preferred_language  ",
        "  English  ",
        "  preference  ",
        8,
    )

    assert result == (
        "preferred_language",
        "English",
        "preference",
    )


@pytest.mark.parametrize(
    "fields",
    [
        ("", "value", "preference", 5),
        ("key", "", "preference", 5),
        ("key", "value", "", 5),
        ("x" * 201, "value", "preference", 5),
        ("key", "value", "x" * 41, 5),
        ("key", "value", "preference", 0),
        ("key", "value", "preference", 11),
        ("key", "value", "preference", True),
        ("key", "value", "preference", 5.5),
    ],
)
def test_validate_memory_fields_rejects_invalid_values(fields):
    with pytest.raises(ValueError):
        _validate_memory_fields(*fields)


def test_upsert_global_memory_builds_correct_conflict_target():
    db = MagicMock()
    expected_memory = MagicMock(spec=UserMemory)
    db.execute.return_value.scalar_one.return_value = expected_memory

    result = upsert_user_memory(
        db,
        memory_key="preferred_language",
        memory_value="English",
        memory_type="preference",
        importance=8,
    )

    assert result is expected_memory
    db.execute.assert_called_once()

    statement = db.execute.call_args.args[0]
    compiled = str(
        statement.compile(dialect=postgresql.dialect())
    )

    assert "ON CONFLICT (memory_key)" in compiled
    assert "source_conversation_id IS NULL" in compiled
    assert "DO UPDATE SET" in compiled
    assert "is_active =" in compiled
    assert True in statement.compile(
        dialect=postgresql.dialect()
    ).params.values()


def test_upsert_conversation_memory_builds_correct_conflict_target():
    db = MagicMock()
    conversation_id = uuid4()
    expected_memory = MagicMock(spec=UserMemory)
    db.execute.return_value.scalar_one.return_value = expected_memory

    result = upsert_user_memory(
        db,
        memory_key="project_preference",
        memory_value="Use PostgreSQL indexing",
        memory_type="project",
        importance=9,
        conversation_id=conversation_id,
    )

    assert result is expected_memory

    statement = db.execute.call_args.args[0]
    compiled = str(
        statement.compile(dialect=postgresql.dialect())
    )

    assert (
        "ON CONFLICT (source_conversation_id, memory_key)"
        in compiled
    )
    assert "source_conversation_id IS NOT NULL" in compiled


def test_upsert_does_not_commit_transaction():
    db = MagicMock()
    db.execute.return_value.scalar_one.return_value = MagicMock()

    upsert_user_memory(
        db,
        memory_key="preferred_language",
        memory_value="English",
        memory_type="preference",
    )

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_upsert_rejects_invalid_values_before_database_call():
    db = MagicMock()

    with pytest.raises(ValueError):
        upsert_user_memory(
            db,
            memory_key=" ",
            memory_value="English",
            memory_type="preference",
        )

    db.execute.assert_not_called()


def test_deactivate_global_memory():
    db = MagicMock()
    query = db.query.return_value
    query.filter.return_value = query
    query.update.return_value = 1

    result = deactivate_user_memory(
        db,
        memory_key="preferred_language",
    )

    assert result is True
    db.query.assert_called_once_with(UserMemory)
    query.update.assert_called_once()


def test_deactivate_returns_false_when_memory_not_found():
    db = MagicMock()
    query = db.query.return_value
    query.filter.return_value = query
    query.update.return_value = 0

    result = deactivate_user_memory(
        db,
        memory_key="missing_memory",
    )

    assert result is False


def test_deactivate_conversation_memory():
    db = MagicMock()
    query = db.query.return_value
    query.filter.return_value = query
    query.update.return_value = 1
    conversation_id = uuid4()

    result = deactivate_user_memory(
        db,
        memory_key="project_preference",
        conversation_id=conversation_id,
    )

    assert result is True
    assert query.filter.call_count == 2


def test_deactivate_rejects_empty_key():
    db = MagicMock()

    with pytest.raises(ValueError):
        deactivate_user_memory(db, " ")

    db.query.assert_not_called()


def test_deactivate_does_not_commit_transaction():
    db = MagicMock()
    query = db.query.return_value
    query.filter.return_value = query
    query.update.return_value = 1

    deactivate_user_memory(db, "preferred_language")

    db.commit.assert_not_called()
    db.rollback.assert_not_called()
