import asyncio
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from app.api.tasks import router as tasks_router
from app.api.email import router as email_router
from app.api.conversations import router as conversations_router
from app.agents.mail_agent import process_inbox
from app.services.gmail_service import gmail_is_connected
from app.database.db import Base, engine
from app.models import Task, TaskActivity, EmailMessage


logger = logging.getLogger(__name__)


async def gmail_polling_loop():
    interval = max(
        15,
        int(os.getenv("GMAIL_POLL_INTERVAL_SECONDS", "60")),
    )

    logger.info(
        "Gmail polling loop started. Interval: %s seconds.",
        interval,
    )

    while True:
        try:
            connected = await asyncio.to_thread(gmail_is_connected)

            if connected:
                result = await asyncio.to_thread(process_inbox)
                logger.info("Automatic Gmail polling result: %s", result)

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Automatic Gmail polling failed.")

        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

    polling_task = asyncio.create_task(gmail_polling_loop())

    try:
        yield
    finally:
        polling_task.cancel()

        try:
            await polling_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="AI Workforce API",
    description="Multi-agent task orchestration platform",
    version="0.1.0",
    lifespan=lifespan,
)

cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://" + "localhost:5173",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in cors_origins.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "Welcome to AI Workforce",
        "status": "running",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "AI Workforce Backend",
    }


app.include_router(tasks_router)
app.include_router(email_router)
app.include_router(conversations_router)
