import pytest
from unittest.mock import patch, MagicMock

from app.agents import worker


def make_state():
    return {
        "worker_assignment": "Research AI agents",
        "acceptance_criteria": "Provide accurate findings",
        "execution_plan": ["Research the topic"],
        "review_feedback": "",
    }


def mock_response(content):
    response = MagicMock()
    response.content = content
    return response


def test_valid_worker_output_is_accepted():
    with patch.object(
        worker,
        "invoke_model",
        return_value=mock_response(
            "  Research completed successfully  "
        ),
    ):
        result = worker.worker_execute(make_state())

    assert result["worker_output"] == "Research completed successfully"
    assert result["execution_status"] == "reviewing"


def test_empty_worker_output_is_rejected():
    with patch.object(
        worker,
        "invoke_model",
        return_value=mock_response("   "),
    ):
        with pytest.raises(ValueError, match="empty response"):
            worker.worker_execute(make_state())


def test_oversized_worker_output_is_rejected():
    with patch.object(
        worker,
        "invoke_model",
        return_value=mock_response("A" * 20001),
    ):
        with pytest.raises(ValueError, match="maximum allowed length"):
            worker.worker_execute(make_state())


def test_unsupported_response_type_is_rejected():
    with patch.object(
        worker,
        "invoke_model",
        return_value=mock_response(12345),
    ):
        with pytest.raises(TypeError, match="unsupported content type"):
            worker.worker_execute(make_state())
