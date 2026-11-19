BEGIN;

-- =========================================================
-- 1. CONVERSATIONS
-- =========================================================

CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    title VARCHAR(200),
    status VARCHAR(30) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);

-- =========================================================
-- 2. CONVERSATION MESSAGES
-- =========================================================

CREATE TABLE conversation_messages (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    message_type VARCHAR(30) NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,

    CONSTRAINT fk_conversation_messages_conversation
        FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE
);

CREATE INDEX ix_conversation_messages_conversation_id
    ON conversation_messages(conversation_id);

-- =========================================================
-- 3. TASK BRIEFS
-- =========================================================

CREATE TABLE task_briefs (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL,
    version INTEGER NOT NULL,
    objective TEXT NOT NULL,
    requirements JSONB NOT NULL,
    constraints JSONB NOT NULL,
    expected_output TEXT,
    missing_information JSONB NOT NULL,
    status VARCHAR(30) NOT NULL,
    confirmed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,

    CONSTRAINT fk_task_briefs_conversation
        FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE,

    CONSTRAINT uq_task_brief_conversation_version
        UNIQUE (conversation_id, version)
);

CREATE INDEX ix_task_briefs_conversation_id
    ON task_briefs(conversation_id);

-- =========================================================
-- 4. USER MEMORIES
-- =========================================================

CREATE TABLE user_memories (
    id UUID PRIMARY KEY,
    memory_key VARCHAR(200) NOT NULL,
    memory_value TEXT NOT NULL,
    memory_type VARCHAR(40) NOT NULL,
    source_conversation_id UUID,
    importance INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,

    CONSTRAINT fk_user_memories_source_conversation
        FOREIGN KEY (source_conversation_id)
        REFERENCES conversations(id)
        ON DELETE SET NULL
);

CREATE INDEX ix_user_memories_memory_key
    ON user_memories(memory_key);

CREATE INDEX ix_user_memories_source_conversation_id
    ON user_memories(source_conversation_id);

-- =========================================================
-- 5. EXTEND EXISTING TASKS TABLE
-- =========================================================

ALTER TABLE tasks
    ADD COLUMN conversation_id UUID,
    ADD COLUMN task_brief_id UUID,
    ADD COLUMN execution_route VARCHAR(20),
    ADD COLUMN requires_human_approval BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN human_approval_status VARCHAR(30) NOT NULL DEFAULT 'not_required';

ALTER TABLE tasks
    ADD CONSTRAINT fk_tasks_conversation
        FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE SET NULL,
    ADD CONSTRAINT fk_tasks_task_brief
        FOREIGN KEY (task_brief_id)
        REFERENCES task_briefs(id)
        ON DELETE SET NULL;

CREATE INDEX ix_tasks_conversation_id
    ON tasks(conversation_id);

CREATE INDEX ix_tasks_task_brief_id
    ON tasks(task_brief_id);

COMMIT;
