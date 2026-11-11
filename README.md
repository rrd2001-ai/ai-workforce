# AI Workforce

AI Workforce is a multi-agent task orchestration MVP. Users submit tasks through a React dashboard. A Manager Agent creates an execution plan, a Worker Agent performs the task, and the Manager Agent reviews the result.

## Architecture

```text
User
 |
 v
React Dashboard (Vite)
 |
 v
FastAPI Backend
 |
 v
PostgreSQL
 |
 v
LangGraph Workflow
 |
 +--> Manager Agent: plans the task
 |
 +--> Worker Agent: executes the task
 |
 +--> Manager Agent: reviews the output
         |
         +--> Approved: finalize the result
         |
         +--> Rejected: retry the Worker
                    |
                    +--> Maximum 2 retries
                    +--> Fail after 3 total attempts

