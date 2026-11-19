
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Response,
)
from sqlalchemy.orm import Session

from app.models.task_activity import TaskActivity
from app.models.schemas import (
    TaskRequest,
    TaskResponse,
    TaskListItem,
    TaskActivityResponse,
    TaskBriefConfirmationResponse,
)
from app.models.task import Task
from app.models.conversation import Conversation
from app.models.task_brief import TaskBrief
from app.models.email_message import EmailMessage
from app.database.db import SessionLocal
from app.graph.workflow import workforce_graph
from app.services.history_retrieval import retrieve_history_context


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["Tasks"])


# Background execution function
def execute_task_in_background(task_id: str, user_task: str):

    db: Session = SessionLocal()

    try:
        task_record = (
            db.query(Task)
            .filter(Task.task_id == task_id)
            .first()
        )

        if not task_record:
            logger.error("Task %s not found", task_id)
            return

        history_context = {}

        try:
            history_context = retrieve_history_context(
                db,
                task_record.conversation_id,
                exclude_task_id=task_id,
            )
        except Exception:
            logger.exception(
                "Could not retrieve history for task %s. "
                "Continuing without history context.",
                task_id,
            )

        initial_state = {
            "task_id": task_id,
            "user_task": user_task,
            "history_context": history_context,
            "retry_count": 0,
            "review_status": "pending",
            "execution_status": "planning",
        }

        # Execute the LangGraph workflow
        result = workforce_graph.invoke(initial_state)

        # Save workflow results
        task_record.execution_plan = result.get("execution_plan", [])
        task_record.worker_assignment = result.get("worker_assignment")
        task_record.acceptance_criteria = result.get("acceptance_criteria")
        task_record.worker_output = result.get("worker_output")
        task_record.review_feedback = result.get("review_feedback")
        task_record.review_status = result.get("review_status", "pending")
        task_record.retry_count = result.get("retry_count", 0)
        task_record.execution_status = result.get("execution_status", "failed")
        task_record.final_output = result.get("final_output", "")

        db.commit()

        logger.info(
            "Task %s completed with status %s",
            task_id,
            task_record.execution_status,
        )

    except Exception as error:

        db.rollback()

        task_record = (
            db.query(Task)
            .filter(Task.task_id == task_id)
            .first()
        )

        if task_record:
            task_record.execution_status = "failed"
            task_record.review_feedback = str(error)
            task_record.final_output = "Task execution failed."
            db.commit()

        logger.exception(
            "Background execution failed for task %s",
            task_id,
        )

    finally:
        db.close()


# Create task and schedule background execution
@router.post("/", response_model=TaskResponse, status_code=202)
def create_task(request: TaskRequest, background_tasks: BackgroundTasks):

    task_id = str(uuid4())

    db: Session = SessionLocal()

    try:
        if request.conversation_id is not None:
            conversation = (
                db.query(Conversation)
                .filter(Conversation.id == request.conversation_id)
                .first()
            )

            if not conversation:
                raise HTTPException(
                    status_code=404,
                    detail="Conversation not found",
                )

        task_record = Task(
            task_id=task_id,
            user_task=request.user_task,
            conversation_id=request.conversation_id,
            execution_status="planning",
            review_status="pending",
            retry_count=0,
        )

        db.add(task_record)
        db.commit()

    except HTTPException:
        raise

    except Exception as error:
        db.rollback()
        logger.exception("Could not create task")
        raise HTTPException(
            status_code=500,
            detail=f"Could not create task: {str(error)}",
        )

    finally:
        db.close()

    background_tasks.add_task(
        execute_task_in_background,
        task_id,
        request.user_task,
    )

    return TaskResponse(
        task_id=task_id,
        user_task=request.user_task,
        execution_status="planning",
        execution_plan=[],
        review_status="pending",
        retry_count=0,
        final_output="",
    )


# Confirm a TaskBrief and create its executable Task
@router.post(
    "/confirm-brief/{brief_id}",
    response_model=TaskBriefConfirmationResponse,
    status_code=201,
)
def confirm_task_brief(
    brief_id: UUID,
    background_tasks: BackgroundTasks,
    http_response: Response,
):
    db: Session = SessionLocal()

    task_id = str(uuid4())

    try:
        # Lock the brief to serialize concurrent confirmations.
        brief = (
            db.query(TaskBrief)
            .filter(TaskBrief.id == brief_id)
            .with_for_update()
            .first()
        )

        if not brief:
            raise HTTPException(
                status_code=404,
                detail="Task brief not found.",
            )

        # Idempotency: return the existing task if already created.
        existing_task = (
            db.query(Task)
            .filter(Task.task_brief_id == brief.id)
            .first()
        )

        if existing_task:
            http_response.status_code = 200

            return TaskBriefConfirmationResponse(
                task_brief=brief,
                task=TaskResponse(
                    task_id=existing_task.task_id,
                    user_task=existing_task.user_task,
                    execution_status=existing_task.execution_status,
                    execution_plan=existing_task.execution_plan or [],
                    review_status=existing_task.review_status,
                    retry_count=existing_task.retry_count,
                    final_output=existing_task.final_output or "",
                    created_at=existing_task.created_at,
                ),
            )

        if brief.status != "draft":
            raise HTTPException(
                status_code=409,
                detail="Only draft task briefs can be confirmed.",
            )

        if brief.missing_information:
            raise HTTPException(
                status_code=409,
                detail="Task brief still has missing information.",
            )

        conversation = (
            db.query(Conversation)
            .filter(Conversation.id == brief.conversation_id)
            .first()
        )

        if not conversation:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )

        user_task = brief.objective.strip()

        if not 5 <= len(user_task) <= 5000:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Task brief objective must contain between "
                    "5 and 5000 characters."
                ),
            )

        # Confirm the brief.
        brief.status = "confirmed"
        brief.confirmed_at = datetime.now(timezone.utc)

        # Create exactly one task linked to this brief.
        task_record = Task(
            task_id=task_id,
            user_task=user_task,
            conversation_id=brief.conversation_id,
            task_brief_id=brief.id,
            execution_status="planning",
            review_status="pending",
            retry_count=0,
        )

        db.add(task_record)

        # Persist confirmation and task creation atomically.
        db.flush()
        db.commit()

        # SQLAlchemy has populated the task defaults during flush.
        result = TaskBriefConfirmationResponse(
            task_brief=brief,
            task=TaskResponse(
                task_id=task_record.task_id,
                user_task=task_record.user_task,
                execution_status=task_record.execution_status,
                execution_plan=task_record.execution_plan or [],
                review_status=task_record.review_status,
                retry_count=task_record.retry_count,
                final_output=task_record.final_output or "",
                created_at=task_record.created_at,
            ),
        )

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()

        logger.exception(
            "Could not confirm task brief %s",
            brief_id,
        )

        raise HTTPException(
            status_code=500,
            detail="Could not confirm task brief.",
        )

    finally:
        db.close()

    # Schedule execution only after successful database commit.
    background_tasks.add_task(
        execute_task_in_background,
        task_id,
        user_task,
    )

    return result


# Retrieve one task
@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: str):

    db: Session = SessionLocal()

    try:
        task_record = (
            db.query(Task)
            .filter(Task.task_id == task_id)
            .first()
        )

        if not task_record:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        email_record = (
            db.query(EmailMessage)
            .filter(EmailMessage.task_id == task_record.task_id)
            .first()
        )

        return TaskResponse(
            task_id=task_record.task_id,
            user_task=task_record.user_task,
            execution_status=task_record.execution_status,
            execution_plan=task_record.execution_plan or [],
            review_status=task_record.review_status,
            retry_count=task_record.retry_count,
            final_output=task_record.final_output or "",
            created_at=task_record.created_at,
            email_source=email_record is not None,
            email_sender=email_record.sender_email if email_record else None,
            email_subject=email_record.subject if email_record else None,
            email_record_id=email_record.id if email_record else None,
            reply_status=email_record.reply_status if email_record else None,
            pending_reply=email_record.pending_reply if email_record else None,
        )

    finally:
        db.close()


# Retrieve all tasks
@router.get("/", response_model=list[TaskListItem])
def get_all_tasks():

    db: Session = SessionLocal()

    try:
        tasks = (
            db.query(Task)
            .order_by(Task.created_at.desc())
            .all()
        )

        task_ids = [task.task_id for task in tasks]

        email_records = (
            db.query(EmailMessage)
            .filter(EmailMessage.task_id.in_(task_ids))
            .all()
            if task_ids
            else []
        )

        emails_by_task_id = {
            email.task_id: email
            for email in email_records
        }

        return [
            TaskListItem(
                task_id=task.task_id,
                user_task=task.user_task,
                execution_status=task.execution_status,
                review_status=task.review_status,
                retry_count=task.retry_count,
                created_at=task.created_at,
                email_source=task.task_id in emails_by_task_id,
                email_sender=(
                    emails_by_task_id[task.task_id].sender_email
                    if task.task_id in emails_by_task_id else None
                ),
                email_subject=(
                    emails_by_task_id[task.task_id].subject
                    if task.task_id in emails_by_task_id else None
                ),
                email_record_id=(
                    emails_by_task_id[task.task_id].id
                    if task.task_id in emails_by_task_id else None
                ),
                reply_status=(
                    emails_by_task_id[task.task_id].reply_status
                    if task.task_id in emails_by_task_id else None
                ),
            )
            for task in tasks
        ]

    finally:
        db.close()


# Retrieve task activities
@router.get(
    "/{task_id}/activities",
    response_model=list[TaskActivityResponse],
)
def get_task_activities(task_id: str):

    db = SessionLocal()

    try:
        task = (
            db.query(Task)
            .filter(Task.task_id == task_id)
            .first()
        )

        if not task:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        activities = (
            db.query(TaskActivity)
            .filter(TaskActivity.task_id == task_id)
            .order_by(
                TaskActivity.created_at,
                TaskActivity.id,
            )
            .all()
        )

        return activities

    finally:
        db.close()
