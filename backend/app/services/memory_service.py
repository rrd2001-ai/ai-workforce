from uuid import UUID

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.user_memory import UserMemory


def _validate_memory_fields(
    memory_key: str,
    memory_value: str,
    memory_type: str,
    importance: int,
) -> tuple[str, str, str]:
    if not isinstance(memory_key, str) or not memory_key.strip():
        raise ValueError("memory_key must be a non-empty string.")

    if not isinstance(memory_value, str) or not memory_value.strip():
        raise ValueError("memory_value must be a non-empty string.")

    if not isinstance(memory_type, str) or not memory_type.strip():
        raise ValueError("memory_type must be a non-empty string.")

    memory_key = memory_key.strip()
    memory_value = memory_value.strip()
    memory_type = memory_type.strip()

    if len(memory_key) > 200:
        raise ValueError("memory_key cannot exceed 200 characters.")

    if len(memory_type) > 40:
        raise ValueError("memory_type cannot exceed 40 characters.")

    if isinstance(importance, bool) or not isinstance(importance, int):
        raise ValueError("importance must be an integer from 1 to 10.")

    if not 1 <= importance <= 10:
        raise ValueError("importance must be between 1 and 10.")

    return memory_key, memory_value, memory_type


def upsert_user_memory(
    db: Session,
    memory_key: str,
    memory_value: str,
    memory_type: str,
    importance: int = 5,
    conversation_id: UUID | None = None,
) -> UserMemory:
    """
    Create or update a memory within its global or conversation scope.

    The caller is responsible for committing or rolling back the transaction.
    """
    memory_key, memory_value, memory_type = _validate_memory_fields(
        memory_key,
        memory_value,
        memory_type,
        importance,
    )

    values = {
        "memory_key": memory_key,
        "memory_value": memory_value,
        "memory_type": memory_type,
        "importance": importance,
        "source_conversation_id": conversation_id,
        "is_active": True,
    }

    statement = pg_insert(UserMemory).values(**values)

    if conversation_id is None:
        conflict_target = {
            "index_elements": [UserMemory.memory_key],
            "index_where": text("source_conversation_id IS NULL"),
        }
    else:
        conflict_target = {
            "index_elements": [
                UserMemory.source_conversation_id,
                UserMemory.memory_key,
            ],
            "index_where": text("source_conversation_id IS NOT NULL"),
        }

    statement = statement.on_conflict_do_update(
        **conflict_target,
        set_={
            "memory_value": statement.excluded.memory_value,
            "memory_type": statement.excluded.memory_type,
            "importance": statement.excluded.importance,
            "is_active": True,
            "updated_at": func.now(),
        },
    ).returning(UserMemory)

    return db.execute(statement).scalar_one()


def deactivate_user_memory(
    db: Session,
    memory_key: str,
    conversation_id: UUID | None = None,
) -> bool:
    """
    Deactivate a memory in the specified scope.

    Returns True if an active memory was deactivated, otherwise False.
    The caller is responsible for committing or rolling back the transaction.
    """
    if not isinstance(memory_key, str) or not memory_key.strip():
        raise ValueError("memory_key must be a non-empty string.")

    memory_key = memory_key.strip()

    query = db.query(UserMemory).filter(
        UserMemory.memory_key == memory_key,
        UserMemory.is_active.is_(True),
    )

    if conversation_id is None:
        query = query.filter(
            UserMemory.source_conversation_id.is_(None)
        )
    else:
        query = query.filter(
            UserMemory.source_conversation_id == conversation_id
        )

    affected = query.update(
        {
            UserMemory.is_active: False,
            UserMemory.updated_at: func.now(),
        },
        synchronize_session=False,
    )

    return affected > 0
