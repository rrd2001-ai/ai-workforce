import pytest
from pydantic import ValidationError

from app.models.schemas import TaskRequest


def test_valid_task_is_accepted():
    task = TaskRequest(user_task="Research AI agents")
    assert task.user_task == "Research AI agents"


def test_whitespace_only_task_is_rejected():
    with pytest.raises(ValidationError):
        TaskRequest(user_task="     ")


def test_task_shorter_than_five_characters_is_rejected():
    with pytest.raises(ValidationError):
        TaskRequest(user_task="Hey")


def test_task_over_5000_characters_is_rejected():
    with pytest.raises(ValidationError):
        TaskRequest(user_task="A" * 5001)


def test_task_whitespace_is_trimmed():
    task = TaskRequest(user_task="  Research AI agents  ")
    assert task.user_task == "Research AI agents"
