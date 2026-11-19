
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.task_brief import TaskBrief
from app.models.schemas import (
    ConversationCreate,
    ConversationResponse,
    ConversationMessageCreate,
    ConversationMessageResponse,
    ConversationIntakeRequest,
    ConversationIntakeResponse,
)
from app.services.intake_service import analyze_intake
from app.services.history_retrieval import retrieve_conversation_messages


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"],
)


@router.post(
    "/",
    response_model=ConversationResponse,
    status_code=201,
)
def create_conversation(
    request: ConversationCreate,
    db: Session = Depends(get_db),
):
    conversation = Conversation(
        id=uuid4(),
        title=request.title.strip() if request.title else None,
        status="active",
    )

    try:
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation
    except Exception:
        db.rollback()
        logger.exception("Could not create conversation")
        raise HTTPException(
            status_code=500,
            detail="Could not create conversation.",
        )


@router.get(
    "/",
    response_model=list[ConversationResponse],
)
def list_conversations(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return (
        db.query(Conversation)
        .order_by(
            Conversation.created_at.desc(),
            Conversation.id.desc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
)
def get_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
):
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    return conversation


@router.post(
    "/{conversation_id}/messages",
    response_model=ConversationMessageResponse,
    status_code=201,
)
def add_conversation_message(
    conversation_id: UUID,
    request: ConversationMessageCreate,
    db: Session = Depends(get_db),
):
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    if request.role not in {"system", "user", "assistant"}:
        raise HTTPException(
            status_code=422,
            detail="Role must be system, user, or assistant.",
        )

    message = ConversationMessage(
        id=uuid4(),
        conversation_id=conversation_id,
        role=request.role,
        content=request.content,
        message_type=request.message_type,
        message_metadata=request.metadata,
    )

    try:
        db.add(message)
        db.flush()

        conversation.updated_at = message.created_at

        db.commit()
        db.refresh(message)

        return message

    except Exception:
        db.rollback()
        logger.exception(
            "Could not save message for conversation %s",
            conversation_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Could not save conversation message.",
        )


@router.get(
    "/{conversation_id}/messages",
    response_model=list[ConversationMessageResponse],
)
def list_conversation_messages(
    conversation_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    conversation_exists = (
        db.query(Conversation.id)
        .filter(Conversation.id == conversation_id)
        .first()
    )

    if not conversation_exists:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    return (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.conversation_id == conversation_id
        )
        .order_by(
            ConversationMessage.created_at.asc(),
            ConversationMessage.id.asc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.post(
    "/{conversation_id}/intake",
    response_model=ConversationIntakeResponse,
)
def process_conversation_intake(
    conversation_id: UUID,
    request: ConversationIntakeRequest,
    db: Session = Depends(get_db),
):
    # Lock the conversation to serialize concurrent intake requests.
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .with_for_update()
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    try:
        # Retrieve existing history before saving the latest message.
        history = retrieve_conversation_messages(
            db,
            conversation_id,
        )

        # Retrieve the latest Task Brief.
        current_brief = (
            db.query(TaskBrief)
            .filter(
                TaskBrief.conversation_id == conversation_id,
            )
            .order_by(
                TaskBrief.version.desc(),
            )
            .first()
        )

        brief_data = None

        if current_brief:
            brief_data = {
                "objective": current_brief.objective,
                "requirements": current_brief.requirements,
                "constraints": current_brief.constraints,
                "expected_output": current_brief.expected_output,
                "missing_information": current_brief.missing_information,
                "status": current_brief.status,
            }

        # Create the user's message.
        user_message = ConversationMessage(
            id=uuid4(),
            conversation_id=conversation_id,
            role="user",
            content=request.message,
            message_type="intake",
        )

        db.add(user_message)

        # Master analyzes the request. No task execution happens here.
        try:
            result = analyze_intake(
                user_message=request.message,
                conversation_history=history,
                current_brief=brief_data,
            )

        except ValueError as exc:
            # Invalid model response: preserve the user's message.
            db.rollback()

            db.add(user_message)
            conversation.updated_at = datetime.now(timezone.utc)
            db.commit()

            logger.warning(
                "Invalid intake response for conversation %s: %s",
                conversation_id,
                exc,
            )

            raise HTTPException(
                status_code=502,
                detail="Master could not process the request. Please try again.",
            )

        except HTTPException:
            raise

        except Exception:
            # Provider failure: preserve the user's message.
            db.rollback()

            db.add(user_message)
            conversation.updated_at = datetime.now(timezone.utc)
            db.commit()

            logger.exception(
                "Master failed to analyze intake for conversation %s",
                conversation_id,
            )

            raise HTTPException(
                status_code=500,
                detail="Could not process conversation intake.",
            )

        # Save Master's response.
        assistant_message = ConversationMessage(
            id=uuid4(),
            conversation_id=conversation_id,
            role="assistant",
            content=result["assistant_message"],
            message_type="intake",
        )

        db.add(assistant_message)

        response_brief = None

        if result["status"] == "ready_for_review":
            # Always create a new version instead of overwriting.
            latest_version = (
                current_brief.version if current_brief else 0
            )

            new_brief = TaskBrief(
                id=uuid4(),
                conversation_id=conversation_id,
                version=latest_version + 1,
                objective=result["objective"],
                requirements=result["requirements"],
                constraints=result["constraints"],
                expected_output=result["expected_output"],
                missing_information=result["missing_information"],
                status="draft",
            )

            db.add(new_brief)
            response_brief = new_brief

        conversation.updated_at = datetime.now(timezone.utc)

        # Persist messages and brief atomically.
        db.flush()
        db.commit()

        if response_brief:
            db.refresh(response_brief)

        return ConversationIntakeResponse(
            status=result["status"],
            assistant_message=result["assistant_message"],
            task_brief=response_brief,
        )

    except HTTPException:
        raise

    except Exception:
        db.rollback()

        logger.exception(
            "Could not process intake for conversation %s",
            conversation_id,
        )

        raise HTTPException(
            status_code=500,
            detail="Could not process conversation intake.",
        )
