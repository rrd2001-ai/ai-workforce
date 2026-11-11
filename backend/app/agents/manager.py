from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os
import re

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


def extract_section(text, start, end):
    if start not in text:
        return ""
    section = text.split(start, 1)[1]
    if end and end in section:
        section = section.split(end, 1)[0]
    return section.strip()


def manager_plan(state: dict) -> dict:
    task = state["user_task"]

    prompt = f"""
You are the Manager Agent in an AI Workforce platform.

Understand the user's task, create an execution plan,
assign the work to the Worker Agent, and define acceptance criteria.

User task:
{task}

Return exactly these three sections:

EXECUTION PLAN:
- Step 1
- Step 2
- Step 3

WORKER ASSIGNMENT:
Describe exactly what the Worker Agent must do.

ACCEPTANCE CRITERIA:
- Criterion 1
- Criterion 2
- Criterion 3
"""

    response = llm.invoke(prompt)
    output = extract_text(response.content)

    plan_text = extract_section(
        output, "EXECUTION PLAN:", "WORKER ASSIGNMENT:"
    )
    assignment = extract_section(
        output, "WORKER ASSIGNMENT:", "ACCEPTANCE CRITERIA:"
    )
    criteria = extract_section(
        output, "ACCEPTANCE CRITERIA:", None
    )

    plan = [
        line.strip().lstrip("- ").strip()
        for line in plan_text.splitlines()
        if line.strip().startswith("-")
    ]

    if not plan or not assignment or not criteria:
        raise ValueError(
            "Manager planning response did not contain all required sections."
        )

    return {
        "execution_plan": plan,
        "worker_assignment": assignment,
        "acceptance_criteria": criteria,
        "execution_status": "executing",
        "retry_count": state.get("retry_count", 0),
    }


def manager_review(state: dict) -> dict:
    task = state["user_task"]
    criteria = state.get("acceptance_criteria", "")
    worker_output = state.get("worker_output", "")

    prompt = f"""
You are the Manager Agent responsible for reviewing Worker output.

ORIGINAL USER TASK:
{task}

ACCEPTANCE CRITERIA:
{criteria}

WORKER OUTPUT:
{worker_output}

Review carefully:
1. Does the output address the original task?
2. Does it satisfy the acceptance criteria?
3. Is it detailed and well structured?
4. Are there obvious contradictions?
5. Does it avoid unsupported factual claims?

Reject incomplete or poor-quality work.

Return exactly this format:

REVIEW STATUS: APPROVED or REJECTED

REVIEW FEEDBACK:
Explain your decision and identify improvements needed.
"""

    response = llm.invoke(prompt)
    output = extract_text(response.content)

    status_match = re.search(
        r"(?im)^\s*REVIEW STATUS:\s*(APPROVED|REJECTED)\s*$",
        output,
    )

    feedback = extract_section(
        output, "REVIEW FEEDBACK:", None
    )

    review_status = (
        status_match.group(1).lower()
        if status_match
        else "rejected"
    )

    if not status_match:
        feedback = (
            "Manager review response had an invalid status format. "
            + feedback
        )

    execution_status = (
        "completed" if review_status == "approved" else "reviewing"
    )

    return {
        "review_status": review_status,
        "review_feedback": feedback,
        "execution_status": execution_status,
    }
