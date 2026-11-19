import json
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


def make_history_context():
    return {
        "task_inventory": {
            "tasks": [
                {
                    "task_id": "task-001",
                    "user_task": "Compare Java HashMap and Hashtable",
                    "execution_status": "completed",
                    "review_status": "approved",
                    "created_at": "2026-11-18T10:00:00",
                },
                {
                    "task_id": "task-002",
                    "user_task": "Research top AI support platforms",
                    "execution_status": "completed",
                    "review_status": "approved",
                    "created_at": "2026-11-18T11:00:00",
                },
            ],
            "total_count": 2,
            "returned_count": 2,
            "offset": 0,
            "limit": 100,
            "has_more": False,
        }
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


def test_worker_prompt_includes_historical_task_inventory():
    state = make_state()
    state["history_context"] = make_history_context()

    with patch.object(
        worker,
        "invoke_model",
        return_value=mock_response("Task inventory processed."),
    ) as mock_invoke:

        worker.worker_execute(state)

    prompt = mock_invoke.call_args.args[0]

    assert "HISTORICAL TASK INVENTORY" in prompt
    assert "task-001" in prompt
    assert "Compare Java HashMap and Hashtable" in prompt
    assert "task-002" in prompt
    assert "Research top AI support platforms" in prompt
    assert '"total_count": 2' in prompt
    assert '"returned_count": 2' in prompt


def test_worker_prompt_includes_incomplete_inventory_metadata():
    state = make_state()

    history_context = make_history_context()
    history_context["task_inventory"]["total_count"] = 150
    history_context["task_inventory"]["returned_count"] = 100
    history_context["task_inventory"]["has_more"] = True

    state["history_context"] = history_context

    with patch.object(
        worker,
        "invoke_model",
        return_value=mock_response("Partial inventory processed."),
    ) as mock_invoke:

        worker.worker_execute(state)

    prompt = mock_invoke.call_args.args[0]

    assert '"total_count": 150' in prompt
    assert '"returned_count": 100' in prompt
    assert '"has_more": true' in prompt
    assert "If has_more is true" in prompt


def test_worker_handles_missing_history_context():
    state = make_state()

    with patch.object(
        worker,
        "invoke_model",
        return_value=mock_response("Completed without history."),
    ) as mock_invoke:

        result = worker.worker_execute(state)

    prompt = mock_invoke.call_args.args[0]

    assert "Task inventory is unavailable." in prompt
    assert result["worker_output"] == "Completed without history."


def test_format_task_inventory_returns_valid_json():
    history_context = make_history_context()

    result = worker.format_task_inventory(history_context)
    parsed = json.loads(result)

    assert parsed["total_count"] == 2
    assert parsed["returned_count"] == 2
    assert len(parsed["tasks"]) == 2
    assert parsed["tasks"][0]["task_id"] == "task-001"


def test_format_task_inventory_handles_missing_inventory():
    result = worker.format_task_inventory({})

    assert result == "Task inventory is unavailable."