BEGIN;

-- One memory per key in the global scope.
CREATE UNIQUE INDEX uq_user_memories_global_key
    ON user_memories (memory_key)
    WHERE source_conversation_id IS NULL;

-- One memory per key within each conversation.
CREATE UNIQUE INDEX uq_user_memories_conversation_key
    ON user_memories (source_conversation_id, memory_key)
    WHERE source_conversation_id IS NOT NULL;

COMMIT;
