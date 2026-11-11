from langgraph.graph import StateGraph, END

from app.graph.state import WorkforceState
from app.graph.nodes import (
    manager_plan_node,
    worker_execute_node,
    manager_review_node,
    retry_check_node,
    finalize_result_node,
    fail_task_node,
)


def route_after_review(state: WorkforceState):
    if state.get("review_status") == "approved":
        return "finalize"
    return "retry_check"


def route_after_retry(state: WorkforceState):
    if state.get("retry_count", 0) <= 2:
        return "worker"
    return "fail"


def build_workflow():
    graph = StateGraph(WorkforceState)

    graph.add_node("manager_plan", manager_plan_node)
    graph.add_node("worker", worker_execute_node)
    graph.add_node("manager_review", manager_review_node)
    graph.add_node("retry_check", retry_check_node)
    graph.add_node("finalize", finalize_result_node)
    graph.add_node("fail", fail_task_node)

    graph.set_entry_point("manager_plan")

    graph.add_edge("manager_plan", "worker")
    graph.add_edge("worker", "manager_review")

    graph.add_conditional_edges(
        "manager_review",
        route_after_review,
        {
            "finalize": "finalize",
            "retry_check": "retry_check",
        },
    )

    graph.add_conditional_edges(
        "retry_check",
        route_after_retry,
        {
            "worker": "worker",
            "fail": "fail",
        },
    )

    graph.add_edge("finalize", END)
    graph.add_edge("fail", END)

    return graph.compile()


workforce_graph = build_workflow()
