import logging
import secrets
import time

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import RedirectResponse
from app.database.db import SessionLocal
from app.models.email_message import EmailMessage
from app.models.task import Task
from app.services.gmail_service import send_reply

from app.services.gmail_service import (
    create_oauth_flow,
    save_credentials,
    gmail_is_connected,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/email", tags=["Email"])

# Temporary OAuth state and original Flow storage for the local MVP.
_pending_states = {}
STATE_TTL_SECONDS = 600


@router.get("/connect")
def connect_gmail():
    now = time.time()

    # Remove expired OAuth sessions.
    expired_states = [
        state
        for state, session in _pending_states.items()
        if now - session["created_at"] > STATE_TTL_SECONDS
    ]

    for state in expired_states:
        _pending_states.pop(state, None)

    state = secrets.token_urlsafe(32)

    # Keep the original Flow object, including its PKCE code verifier.
    flow = create_oauth_flow(state=state)

    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    _pending_states[state] = {
        "created_at": now,
        "flow": flow,
    }

    return RedirectResponse(
        url=authorization_url,
        status_code=302,
    )


@router.get("/oauth/callback")
def gmail_oauth_callback(code: str = None, state: str = None, error: str = None):
    if error:
        if state:
            _pending_states.pop(state, None)

        raise HTTPException(
            status_code=400,
            detail="Google authorization was not completed.",
        )

    if not code or not state:
        raise HTTPException(
            status_code=400,
            detail="Missing OAuth authorization parameters.",
        )

    session = _pending_states.pop(state, None)

    if session is None or time.time() - session["created_at"] > STATE_TTL_SECONDS:
        raise HTTPException(
            status_code=400,
            detail="OAuth state is invalid or expired. Please reconnect Gmail.",
        )

    try:
        # Reuse the original Flow so its PKCE verifier is preserved.
        flow = session["flow"]
        flow.fetch_token(code=code)

        credentials = flow.credentials
        save_credentials(credentials)

        return {
            "status": "connected",
            "message": "Gmail authorization successful.",
        }

    except Exception:
        logger.exception("Gmail OAuth callback failed")
        raise HTTPException(
            status_code=400,
            detail="Gmail authorization failed. Check backend logs for details.",
        )


@router.get("/status")
def gmail_status():
    return {
        "connected": gmail_is_connected(),
    }


from app.agents.mail_agent import process_inbox


@router.post("/check-inbox", status_code=202)
def check_inbox(background_tasks: BackgroundTasks):
    if not gmail_is_connected():
        raise HTTPException(
            status_code=400,
            detail="Gmail is not connected. Connect Gmail first.",
        )

    background_tasks.add_task(process_inbox)

    return {
        "status": "started",
        "message": "Inbox processing has been queued.",
    }



@router.get("/pending-replies")
def get_pending_replies():
    db = SessionLocal()

    try:
        records = (
            db.query(EmailMessage)
            .filter(
                EmailMessage.reply_status == "pending_approval"
            )
            .order_by(EmailMessage.created_at.desc())
            .all()
        )

        return {
            "count": len(records),
            "pending_replies": [
                {
                    "id": record.id,
                    "sender_email": record.sender_email,
                    "subject": record.subject,
                    "pending_reply": record.pending_reply,
                    "task_id": record.task_id,
                    "received_at": record.received_at,
                }
                for record in records
            ],
        }
    finally:
        db.close()


from app.agents.mail_agent import get_allowed_senders


@router.post("/{email_id}/approve")
def approve_and_send_reply(email_id: int):
    if not gmail_is_connected():
        raise HTTPException(
            status_code=400,
            detail="Gmail is not connected.",
        )

    db = SessionLocal()

    try:
        record = (
            db.query(EmailMessage)
            .filter(EmailMessage.id == email_id)
            .with_for_update()
            .first()
        )

        if record is None:
            raise HTTPException(
                status_code=404,
                detail="Email record not found.",
            )

        if record.reply_status != "pending_approval":
            raise HTTPException(
                status_code=409,
                detail="This reply is not waiting for approval.",
            )

        task = (
            db.query(Task)
            .filter(Task.task_id == record.task_id)
            .first()
        )

        if (
            task is None
            or task.execution_status != "completed"
            or task.review_status != "approved"
            or not task.final_output
        ):
            raise HTTPException(
                status_code=409,
                detail="The linked task has not been completed and approved.",
            )

        if record.pending_reply != task.final_output:
            raise HTTPException(
                status_code=409,
                detail="The pending reply does not match the approved task output.",
            )

        if record.sender_email.lower() not in get_allowed_senders():
            raise HTTPException(
                status_code=403,
                detail="The original sender is not authorized.",
            )

        record.reply_status = "sending"
        db.commit()

        try:
            result = send_reply(
                gmail_message_id=record.gmail_message_id,
                thread_id=record.thread_id,
                recipient=record.sender_email,
                subject=record.subject or "",
                body=record.pending_reply,
            )
        except Exception:
            logger.exception("Gmail reply sending failed.")
            record.reply_status = "send_failed"
            db.commit()

            raise HTTPException(
                status_code=502,
                detail=(
                    "Gmail could not confirm the reply was sent. "
                    "Check the Gmail thread before attempting another send."
                ),
            )

        record.sent_message_id = result["sent_message_id"]
        record.reply_status = "sent"
        db.commit()

        return {
            "status": "sent",
            "email_id": record.id,
            "sent_message_id": record.sent_message_id,
            "thread_id": record.thread_id,
        }

    finally:
        db.close()
