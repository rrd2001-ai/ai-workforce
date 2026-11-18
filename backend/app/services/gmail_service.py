import os
import base64
import re
from email.message import EmailMessage as MIMEEmailMessage
from email.utils import parseaddr
from html import unescape
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build


load_dotenv()

GMAIL_SCOPES = [
    "https://" + "www.googleapis.com/auth/gmail.readonly",
    "https://" + "www.googleapis.com/auth/gmail.send",
]

TOKEN_PATH = Path(__file__).resolve().parents[2] / "gmail_token.json"


def get_oauth_client_config():
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")

    if not client_id or not client_secret or not redirect_uri:
        raise RuntimeError("Google OAuth configuration is incomplete.")

    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://" + "accounts.google.com/o/oauth2/auth",
            "token_uri": "https://" + "oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }


def create_oauth_flow(state=None):
    flow = Flow.from_client_config(
        get_oauth_client_config(),
        scopes=GMAIL_SCOPES,
        state=state,
    )

    flow.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    return flow


def save_credentials(credentials):
    TOKEN_PATH.write_text(credentials.to_json())
    TOKEN_PATH.chmod(0o600)


def load_credentials():
    if not TOKEN_PATH.exists():
        return None

    credentials = Credentials.from_authorized_user_file(
        str(TOKEN_PATH),
        scopes=GMAIL_SCOPES,
    )

    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        save_credentials(credentials)

    if not credentials.valid:
        return None

    return credentials


def get_gmail_service():
    credentials = load_credentials()

    if credentials is None:
        raise RuntimeError(
            "Gmail is not connected. Complete Google OAuth first."
        )

    return build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False,
    )


def gmail_is_connected():
    try:
        return load_credentials() is not None
    except Exception:
        return False


def _decode_gmail_body(data):
    if not data:
        return ""

    decoded = base64.urlsafe_b64decode(
        data + "=" * (-len(data) % 4)
    )

    return decoded.decode("utf-8", errors="replace")


def _extract_message_body(payload):
    plain_parts = []
    html_parts = []

    def walk(part):
        mime_type = part.get("mimeType", "")
        body_data = part.get("body", {}).get("data")

        if mime_type == "text/plain" and body_data:
            plain_parts.append(_decode_gmail_body(body_data))

        elif mime_type == "text/html" and body_data:
            html_parts.append(_decode_gmail_body(body_data))

        for child in part.get("parts", []):
            walk(child)

    walk(payload or {})

    if plain_parts:
        return "\n".join(plain_parts).strip()

    if html_parts:
        html = "\n".join(html_parts)

        html = re.sub(
            r"<(script|style)\b[^>]*>.*?</\1>",
            "",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )

        html = re.sub(r"<[^>]+>", " ", html)

        return unescape(
            re.sub(r"\s+", " ", html)
        ).strip()

    return ""


def get_inbox_messages(max_results=20):
    service = get_gmail_service()

    response = (
        service.users()
        .messages()
        .list(
            userId="me",
            labelIds=["INBOX"],
            q="is:unread",
            maxResults=max_results,
        )
        .execute()
    )

    messages = response.get("messages", [])
    results = []

    for item in messages:
        message = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=item["id"],
                format="full",
            )
            .execute()
        )

        headers = {
            header["name"].lower(): header["value"]
            for header in message.get("payload", {}).get("headers", [])
        }

        internal_date = message.get("internalDate")

        results.append({
            "gmail_message_id": message["id"],
            "thread_id": message["threadId"],
            "sender": headers.get("from", ""),
            "subject": headers.get("subject", ""),
            "message_id_header": headers.get("message-id", ""),
            "body": _extract_message_body(
                message.get("payload", {})
            ),
            "snippet": message.get("snippet", ""),
            "internal_date": internal_date,
        })

    return results


def send_reply(
    gmail_message_id,
    thread_id,
    recipient,
    subject,
    body,
):
    parsed_recipient = parseaddr(recipient or "")[1].strip().lower()

    if not parsed_recipient or parsed_recipient != recipient.strip().lower():
        raise ValueError("Invalid reply recipient.")

    if any(char in parsed_recipient for char in "\r\n"):
        raise ValueError("Invalid reply recipient.")

    clean_subject = (subject or "").replace("\\r", " ").replace("\\n", " ").strip()

    if not clean_subject.lower().startswith("re:"):
        clean_subject = f"Re: {clean_subject}"

    service = get_gmail_service()

    original = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=gmail_message_id,
            format="metadata",
            metadataHeaders=["Message-ID", "References"],
        )
        .execute()
    )

    headers = {
        header["name"].lower(): header["value"]
        for header in original.get("payload", {}).get("headers", [])
    }

    original_message_id = headers.get("message-id")

    if not original_message_id:
        raise RuntimeError("Original email Message-ID header is missing.")

    reply = MIMEEmailMessage()
    reply["To"] = parsed_recipient
    reply["Subject"] = clean_subject
    reply["In-Reply-To"] = original_message_id

    references = headers.get("references", "").strip()
    reply["References"] = (
        f"{references} {original_message_id}".strip()
        if references
        else original_message_id
    )

    reply.set_content(body or "")

    raw_message = base64.urlsafe_b64encode(
        reply.as_bytes()
    ).decode("utf-8")

    sent = (
        service.users()
        .messages()
        .send(
            userId="me",
            body={
                "raw": raw_message,
                "threadId": thread_id,
            },
        )
        .execute()
    )

    return {
        "sent_message_id": sent["id"],
        "thread_id": sent.get("threadId", thread_id),
    }
