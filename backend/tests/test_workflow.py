from app.graph.workflow import (
    route_after_review,
    route_after_retry,
)


def test_approved_review():
    assert route_after_review({"review_status": "approved"}) == "finalize"


def test_rejected_review():
    assert route_after_review({"review_status": "rejected"}) == "retry_check"


def test_first_retry():
    assert route_after_retry({"retry_count": 1}) == "worker"


def test_second_retry():
    assert route_after_retry({"retry_count": 2}) == "worker"


def test_retry_limit_exceeded():
    assert route_after_retry({"retry_count": 3}) == "fail"


def test_rejected_output_is_retried_and_approved(monkeypatch):
    from app.graph import nodes
    from app.graph.workflow import build_workflow

    worker_attempts = {"count": 0}
    review_attempts = {"count": 0}

    def fake_plan(state):
        return {
            "execution_plan": ["Execute test task"],
            "worker_assignment": "Complete the test task",
            "acceptance_criteria": "Produce valid output",
        }

    def fake_worker(state):
        worker_attempts["count"] += 1
        return {
            "worker_output": f"Test output attempt {worker_attempts['count']}",
            "execution_status": "reviewing",
        }

    def fake_review(state):
        review_attempts["count"] += 1

        if review_attempts["count"] == 1:
            return {
                "review_status": "rejected",
                "review_feedback": "Add more detail.",
                "execution_status": "reviewing",
            }

        return {
            "review_status": "approved",
            "review_feedback": "Output meets requirements.",
            "execution_status": "completed",
        }

    monkeypatch.setattr(nodes, "manager_plan", fake_plan)
    monkeypatch.setattr(nodes, "worker_execute", fake_worker)
    monkeypatch.setattr(nodes, "manager_review", fake_review)

    graph = build_workflow()

    result = graph.invoke({
        "user_task": "Test retry workflow",
        "retry_count": 0,
        "review_status": "pending",
        "execution_status": "planning",
    })

    assert worker_attempts["count"] == 2
    assert review_attempts["count"] == 2
    assert result["retry_count"] == 1
    assert result["review_status"] == "approved"
    assert result["execution_status"] == "completed"
    assert result["final_output"] == "Test output attempt 2"


def test_workflow_fails_after_maximum_retries(monkeypatch):
    from app.graph import nodes
    from app.graph.workflow import build_workflow

    worker_attempts = {"count": 0}

    def fake_plan(state):
        return {
            "execution_plan": ["Execute test task"],
            "worker_assignment": "Complete the test task",
            "acceptance_criteria": "Produce valid output",
        }

    def fake_worker(state):
        worker_attempts["count"] += 1
        return {
            "worker_output": "Incomplete test output",
            "execution_status": "reviewing",
        }

    def fake_review(state):
        return {
            "review_status": "rejected",
            "review_feedback": "Output is incomplete.",
            "execution_status": "reviewing",
        }

    monkeypatch.setattr(nodes, "manager_plan", fake_plan)
    monkeypatch.setattr(nodes, "worker_execute", fake_worker)
    monkeypatch.setattr(nodes, "manager_review", fake_review)

    graph = build_workflow()

    result = graph.invoke({
        "user_task": "Test retry exhaustion",
        "retry_count": 0,
        "review_status": "pending",
        "execution_status": "planning",
    })

    assert worker_attempts["count"] == 3
    assert result["retry_count"] == 3
    assert result["review_status"] == "rejected"
    assert result["execution_status"] == "failed"
    assert "maximum of 2 retries" in result["final_output"]
