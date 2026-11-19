
import pytest

from unittest.mock import patch

from app.services.intake_service import (
    IntakeResponse,
    _parse_model_response,
    analyze_intake,
)


def test_analyze_intake_returns_clarification_when_information_is_missing():
    model_response = IntakeResponse(
        status="needs_clarification",
        assistant_message=(
            "Which programming language should the application use?"
        ),
        objective="Build a web application",
        requirements=["Users can create accounts"],
        constraints=[],
        expected_output="A working web application",
        missing_information=["Preferred programming language"],
    )

    with patch(
        "app.services.intake_service.manager.invoke_structured_model",
        return_value=model_response,
    ) as mock_invoke:
        result = analyze_intake(
            user_message="Build a web application where users can create accounts",
            conversation_history=[],
            current_brief=None,
        )

    mock_invoke.assert_called_once()

    assert result["status"] == "needs_clarification"
    assert result["assistant_message"]
    assert "Preferred programming language" in result["missing_information"]


def test_analyze_intake_returns_ready_for_review_when_information_is_sufficient():
    model_response = IntakeResponse(
        status="ready_for_review",
        assistant_message="Please review the task brief before I start.",
        objective="Build a task management web application",
        requirements=[
            "Users can create tasks",
            "Users can update task status",
        ],
        constraints=["Use Java and Spring Boot"],
        expected_output="A working task management application",
        missing_information=[],
    )

    with patch(
        "app.services.intake_service.manager.invoke_structured_model",
        return_value=model_response,
    ) as mock_invoke:
        result = analyze_intake(
            user_message=(
                "Build a task management application using Java and "
                "Spring Boot. Users should create tasks and update "
                "their status."
            ),
            conversation_history=[],
            current_brief=None,
        )

    mock_invoke.assert_called_once()

    assert result["status"] == "ready_for_review"
    assert result["objective"] == "Build a task management web application"
    assert len(result["requirements"]) == 2
    assert result["missing_information"] == []


def test_parse_model_response_rejects_invalid_json():
    with pytest.raises(ValueError, match="invalid JSON"):
        _parse_model_response("not valid json")


def test_parse_model_response_rejects_unsupported_status():
    response = """
    {
        "status": "completed",
        "assistant_message": "Done",
        "objective": "Build an application",
        "requirements": [],
        "constraints": [],
        "expected_output": "Application",
        "missing_information": []
    }
    """

    with pytest.raises(ValueError, match="unsupported intake status"):
        _parse_model_response(response)


def test_parse_model_response_rejects_missing_assistant_message():
    response = """
    {
        "status": "ready_for_review",
        "objective": "Build an application",
        "requirements": [],
        "constraints": [],
        "expected_output": "Application",
        "missing_information": []
    }
    """

    with pytest.raises(ValueError, match="assistant message"):
        _parse_model_response(response)


def test_parse_model_response_rejects_invalid_requirements():
    response = """
    {
        "status": "ready_for_review",
        "assistant_message": "Review the brief",
        "objective": "Build an application",
        "requirements": "Users can log in",
        "constraints": [],
        "expected_output": "Application",
        "missing_information": []
    }
    """

    with pytest.raises(ValueError, match="requirements must be a list"):
        _parse_model_response(response)


def test_parse_model_response_rejects_clarification_without_missing_information():
    response = """
    {
        "status": "needs_clarification",
        "assistant_message": "Please clarify",
        "objective": "Build an application",
        "requirements": [],
        "constraints": [],
        "expected_output": "Application",
        "missing_information": []
    }
    """

    with pytest.raises(ValueError, match="requires missing information"):
        _parse_model_response(response)


def test_parse_model_response_rejects_ready_brief_with_missing_information():
    response = """
    {
        "status": "ready_for_review",
        "assistant_message": "Review the brief",
        "objective": "Build an application",
        "requirements": [],
        "constraints": [],
        "expected_output": "Application",
        "missing_information": ["Preferred programming language"]
    }
    """

    with pytest.raises(ValueError, match="while information is missing"):
        _parse_model_response(response)


def test_analyze_intake_rejects_empty_user_message():
    with pytest.raises(ValueError, match="user_message cannot be empty"):
        analyze_intake(
            user_message="   ",
            conversation_history=[],
            current_brief=None,
        )


def test_analyze_intake_rejects_non_list_conversation_history():
    with pytest.raises(ValueError, match="conversation_history must be a list"):
        analyze_intake(
            user_message="Build an application",
            conversation_history="invalid history",
            current_brief=None,
        )


def test_analyze_intake_rejects_oversized_conversation_history():
    with pytest.raises(ValueError, match="history exceeds the maximum length"):
        analyze_intake(
            user_message="Build an application",
            conversation_history=["x" * 13_000],
            current_brief=None,
        )


def test_analyze_intake_rejects_oversized_current_brief():
    with pytest.raises(ValueError, match="brief exceeds the maximum length"):
        analyze_intake(
            user_message="Update the application",
            conversation_history=[],
            current_brief={"objective": "x" * 13_000},
        )
