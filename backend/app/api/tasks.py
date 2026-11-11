
import logging
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from app.models.task_activity import TaskActivity
from app.models.schemas import TaskRequest, TaskResponse, TaskListItem, TaskActivityResponse
from app.models.task import Task
from app.database.db import SessionLocal
from app.graph.workflow import workforce_graph


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

        initial_state = {
            "task_id": task_id,
            "user_task": user_task,
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

        logger.info("Task %s completed with status %s",
                    task_id, task_record.execution_status)

    except Exception as error:

        db.rollback()

        # Record execution failure
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

        logger.exception("Background execution failed for task %s", task_id)

    finally:
        db.close()


# Create task and schedule background execution
@router.post("/", response_model=TaskResponse, status_code=202)
def create_task(request: TaskRequest, background_tasks: BackgroundTasks):

    task_id = str(uuid4())

    db: Session = SessionLocal()

    try:
        task_record = Task(
            task_id=task_id,
            user_task=request.user_task,
            execution_status="planning",
            review_status="pending",
            retry_count=0,
        )

        db.add(task_record)
        db.commit()

    except Exception as error:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Could not create task: {str(error)}"
        )

    finally:
        db.close()

    # Schedule execution after the response is sent
    background_tasks.add_task(
        execute_task_in_background,
        task_id,
        request.user_task,
    )

    # Return immediately
    return TaskResponse(
        task_id=task_id,
        user_task=request.user_task,
        execution_status="planning",
        execution_plan=[],
        review_status="pending",
        retry_count=0,
        final_output="",
    )


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
                detail="Task not found"
            )

        return TaskResponse(
            task_id=task_record.task_id,
            user_task=task_record.user_task,
            execution_status=task_record.execution_status,
            execution_plan=task_record.execution_plan or [],
            review_status=task_record.review_status,
            retry_count=task_record.retry_count,
            final_output=task_record.final_output or "",
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

        return [
            TaskListItem(
                task_id=task.task_id,
                user_task=task.user_task,
                execution_status=task.execution_status,
                review_status=task.review_status,
                retry_count=task.retry_count,
                created_at=task.created_at,
            )
            for task in tasks
        ]

    finally:
        db.close()



@router.get(
    "/{task_id}/activities",
    response_model=list[TaskActivityResponse],
)
def get_task_activities(task_id: str):
    db = SessionLocal()

    try:
        task = db.query(Task).filter(
            Task.task_id == task_id
        ).first()

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
