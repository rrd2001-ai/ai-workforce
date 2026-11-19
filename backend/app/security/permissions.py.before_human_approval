from enum import Enum


class AgentRole(str, Enum):
    MASTER = "master"
    WORKER = "worker"
    MAIL = "mail"


class AgentAction(str, Enum):
    PLAN_TASK = "plan_task"
    DELEGATE_TASK = "delegate_task"
    COMMUNICATE_WITH_AGENTS = "communicate_with_agents"

    EXECUTE_ASSIGNED_WORK = "execute_assigned_work"

    REVIEW_OUTPUT = "review_output"
    APPROVE_OUTPUT = "approve_output"
    REJECT_OUTPUT = "reject_output"

    PROCESS_EMAIL = "process_email"
    SEND_EMAIL_REPLY = "send_email_reply"


AGENT_PERMISSIONS = {
    AgentRole.MASTER: {
        AgentAction.PLAN_TASK,
        AgentAction.DELEGATE_TASK,
        AgentAction.COMMUNICATE_WITH_AGENTS,
        AgentAction.REVIEW_OUTPUT,
        AgentAction.APPROVE_OUTPUT,
        AgentAction.REJECT_OUTPUT,
    },
    AgentRole.WORKER: {
        AgentAction.EXECUTE_ASSIGNED_WORK,
    },
    AgentRole.MAIL: {
        AgentAction.PROCESS_EMAIL,
        AgentAction.SEND_EMAIL_REPLY,
    },
}


def check_permission(role: AgentRole, action: AgentAction) -> bool:
    """Check whether an agent role has a specific capability."""
    return action in AGENT_PERMISSIONS.get(role, set())


def require_permission(role: AgentRole, action: AgentAction) -> None:
    """Raise an error when an agent attempts an unauthorized action."""
    if not check_permission(role, action):
        raise PermissionError(
            f"Agent '{role.value}' is not allowed to perform "
            f"'{action.value}'."
        )
