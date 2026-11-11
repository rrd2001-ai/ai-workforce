from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.models.task_activity import TaskActivity


def log_activity(
    task_id: str,
    agent_name: str,
    activity_type: str,
    status: str,
    message: str,
):
    db: Session = SessionLocal()

    try:
        activity = TaskActivity(
            task_id=task_id,
            agent_name=agent_name,
            activity_type=activity_type,
            status=status,
            message=message,
        )

        db.add(activity)
        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
