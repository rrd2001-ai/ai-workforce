
import pytest
from unittest.mock import patch, MagicMock

from app.agents import manager


def make_plan_state():
    return {
        "user_task": "Research AI agent architectures",
        "retry_count": 0,
    }


def make_review_state():
    return {
        "user_task": "Research AI agent architectures",
        "acceptance_criteria": "Include accurate and relevant findings",
        "worker_output": "The report covers major architectures.",
    }


def mock_response(content):
    response = MagicMock()
    response.content = content
    return response


def test_valid_manager_plan_is_accepted():
    response = """
EXECUTION PLAN:

- Research the topic
- Compare approaches

WORKER ASSIGNMENT:

Research AI agent architectures and compare approaches.

ACCEPTANCE CRITERIA:

- Include accurate findings
- Explain key differences
"""

    with patch.object(
        manager, "invoke_model", return_value=mock_response(response)
    ):
        result = manager.manager_plan(make_plan_state())

    assert result["execution_plan"] == [
        "Research the topic",
        "Compare approaches",
    ]
    assert result["worker_assignment"]
    assert result["acceptance_criteria"]
    assert result["execution_status"] == "executing"


def test_incomplete_manager_plan_is_rejected():
    response = """
EXECUTION PLAN:

- Research the topic
"""

    with patch.object(
        manager, "invoke_model", return_value=mock_response(response)
    ):
        with pytest.raises(ValueError, match="required sections"):
            manager.manager_plan(make_plan_state())


def test_valid_manager_review_is_accepted():
    response = """
REVIEW STATUS: APPROVED

REVIEW FEEDBACK:

The output meets the acceptance criteria.
"""

    with patch.object(
        manager, "invoke_model", return_value=mock_response(response)
    ):
        result = manager.manager_review(make_review_state())

    assert result["review_status"] == "approved"
    assert result["execution_status"] == "completed"
    assert "meets the acceptance criteria" in result["review_feedback"]


def test_invalid_manager_review_defaults_to_rejected():
    response = """
The output looks good.
"""

    with patch.object(
        manager, "invoke_model", return_value=mock_response(response)
    ):
        result = manager.manager_review(make_review_state())

    assert result["review_status"] == "rejected"
    assert result["execution_status"] == "reviewing"
    assert "invalid status format" in result["review_feedback"]


def test_manager_rejects_more_than_ten_plan_steps():
    steps = "\n".join(f"- Step {i}" for i in range(1, 12))

    response = f"""
EXECUTION PLAN:

{steps}

WORKER ASSIGNMENT:

Research the topic.

ACCEPTANCE CRITERIA:

- Include accurate findings.
"""

    with patch.object(
        manager, "invoke_model", return_value=mock_response(response)
    ):
        with pytest.raises(ValueError, match="maximum of 10 steps"):
            manager.manager_plan(make_plan_state())


def test_manager_rejects_oversized_assignment():
    response = f"""
EXECUTION PLAN:

- Research the topic

WORKER ASSIGNMENT:

{"A" * 3001}

ACCEPTANCE CRITERIA:

- Include accurate findings.
"""

    with patch.object(
        manager, "invoke_model", return_value=mock_response(response)
    ):
        with pytest.raises(ValueError, match="assignment"):
            manager.manager_plan(make_plan_state())


def test_manager_rejects_oversized_criteria():
    response = f"""
EXECUTION PLAN:

- Research the topic

WORKER ASSIGNMENT:

Research the topic.

ACCEPTANCE CRITERIA:

{"A" * 3001}
"""

    with patch.object(
        manager, "invoke_model", return_value=mock_response(response)
    ):
        with pytest.raises(ValueError, match="criteria"):
            manager.manager_plan(make_plan_state())


def test_manager_rejects_oversized_response():
    response = "A" * 20001

    with patch.object(
        manager, "invoke_model", return_value=mock_response(response)
    ):
        with pytest.raises(ValueError, match="response"):
            manager.manager_plan(make_plan_state())


def test_manager_rejects_empty_response():
    with patch.object(
        manager, "invoke_model", return_value=mock_response("   ")
    ):
        with pytest.raises(ValueError, match="empty response"):
            manager.manager_plan(make_plan_state())
