import pytest

from app.graph import nodes

from app.security.permissions import (
    AgentRole,
    AGENT_PERMISSIONS,
)


def test_master_planning_is_blocked_without_permission(monkeypatch):
    monkeypatch.setitem(
        AGENT_PERMISSIONS,
        AgentRole.MASTER,
        set(),
    )

    def should_not_execute(state):
        pytest.fail("Master executed without permission")

    monkeypatch.setattr(nodes, "manager_plan", should_not_execute)

    with pytest.raises(PermissionError):
        nodes.manager_plan_node({"user_task": "Test task"})


def test_worker_execution_is_blocked_without_permission(monkeypatch):
    monkeypatch.setitem(
        AGENT_PERMISSIONS,
        AgentRole.WORKER,
        set(),
    )

    def should_not_execute(state):
        pytest.fail("Worker executed without permission")

    monkeypatch.setattr(nodes, "worker_execute", should_not_execute)

    with pytest.raises(PermissionError):
        nodes.worker_execute_node({"worker_assignment": "Test"})


def test_master_review_is_blocked_without_permission(monkeypatch):
    monkeypatch.setitem(
        AGENT_PERMISSIONS,
        AgentRole.MASTER,
        set(),
    )

    def should_not_execute(state):
        pytest.fail("Master reviewed without permission")

    monkeypatch.setattr(nodes, "manager_review", should_not_execute)

    with pytest.raises(PermissionError):
        nodes.manager_review_node({"user_task": "Test task"})