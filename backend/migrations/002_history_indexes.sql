BEGIN;

-- Recent conversation listing
CREATE INDEX ix_conversations_created_at
    ON conversations (created_at);

-- Chronological messages within a conversation
CREATE INDEX ix_conversation_messages_conversation_created
    ON conversation_messages (conversation_id, created_at, id);

-- Existing task list sorted by creation time
CREATE INDEX ix_tasks_created_at
    ON tasks (created_at);

-- Tasks belonging to a conversation, sorted chronologically
CREATE INDEX ix_tasks_conversation_created
    ON tasks (conversation_id, created_at);

-- Chronological activity history for a task
CREATE INDEX ix_task_activities_task_created
    ON task_activities (task_id, created_at, id);

-- Remove indexes now covered by the new composite indexes,
-- unique constraints, or primary-key indexes
DROP INDEX ix_conversation_messages_conversation_id;
DROP INDEX ix_task_briefs_conversation_id;
DROP INDEX ix_tasks_id;
DROP INDEX ix_tasks_conversation_id;
DROP INDEX ix_task_activities_id;
DROP INDEX ix_task_activities_task_id;

COMMIT;
