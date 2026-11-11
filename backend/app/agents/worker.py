from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    timeout=45,
    max_retries=1,
)


def extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict)
            and block.get("type") == "text"
        )
    return str(content)


def worker_execute(state: dict) -> dict:
    assignment = state["worker_assignment"]
    criteria = state.get("acceptance_criteria", "")
    plan = state.get("execution_plan", [])
    feedback = state.get("review_feedback", "")

    prompt = f"""
You are the Worker Agent in an AI Workforce platform.

Your responsibility is to execute the assignment from the Manager Agent.

EXECUTION PLAN:
{plan}

YOUR ASSIGNMENT:
{assignment}

ACCEPTANCE CRITERIA:
{criteria}

MANAGER FEEDBACK FROM PREVIOUS REVIEW:
{feedback if feedback else "No previous feedback. This is the initial execution."}

GENERAL INSTRUCTIONS:
1. Follow the execution plan.
2. Address the acceptance criteria.
3. Correct problems identified in previous review feedback.
4. Return professional, structured Markdown.
5. Never fabricate facts, sources, statistics or URLs.
6. Clearly identify uncertainty when relevant.
"""

    response = llm.invoke(prompt)
    output = extract_text(response.content)

    if not output.strip():
        raise ValueError("Worker returned an empty response.")

    return {
        "worker_output": output,
        "execution_status": "reviewing",
    }
