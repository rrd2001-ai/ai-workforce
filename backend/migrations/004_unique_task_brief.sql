BEGIN;

-- A confirmed TaskBrief must produce at most one Task.
-- Multiple direct tasks with NULL task_brief_id remain allowed.

DROP INDEX IF EXISTS ix_tasks_task_brief_id;

CREATE UNIQUE INDEX uq_tasks_task_brief_id
    ON tasks (task_brief_id)
    WHERE task_brief_id IS NOT NULL;

COMMIT;
