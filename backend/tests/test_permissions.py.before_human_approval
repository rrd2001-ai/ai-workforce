import pytest

from app.security.permissions import (
    AgentRole,
    AgentAction,
    check_permission,
    require_permission,
)


def test_master_can_delegate():
    assert check_permission(
        AgentRole.MASTER,
        AgentAction.DELEGATE_TASK,
    )


def test_worker_can_execute_assigned_work():
    assert check_permission(
        AgentRole.WORKER,
        AgentAction.EXECUTE_ASSIGNED_WORK,
    )


def test_mail_agent_can_process_email():
    assert check_permission(
        AgentRole.MAIL,
        AgentAction.PROCESS_EMAIL,
    )


def test_worker_cannot_approve_output():
    with pytest.raises(PermissionError):
        require_permission(
            AgentRole.WORKER,
            AgentAction.APPROVE_OUTPUT,
        )