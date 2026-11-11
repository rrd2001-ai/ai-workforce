
import { useCallback, useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './App.css'
const API = ['http:', '', '127.0.0.1:8000'].join('/')

function formatDate(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

function statusClass(status) {
  return (status || 'pending').toLowerCase()
}

function buildAttemptHistory(activities) {
  const attempts = []

  for (const activity of activities) {
    if (
      activity.agent_name === 'Worker Agent' &&
      activity.activity_type === 'execution' &&
      activity.status === 'started'
    ) {
      attempts.push({
        number: attempts.length + 1,
        reviewStatus: 'pending',
        feedback: '',
        startedAt: activity.created_at,
      })
    }

    if (
      activity.agent_name === 'Manager Agent' &&
      activity.activity_type === 'review' &&
      ['approved', 'rejected'].includes(activity.status)
    ) {
      const currentAttempt = attempts[attempts.length - 1]

      if (currentAttempt) {
        currentAttempt.reviewStatus = activity.status
        currentAttempt.feedback =
          activity.status === 'rejected' ? activity.message : ''
      }
    }
  }

  return attempts
}

function App() {
  const [tasks, setTasks] = useState([])
  const [selectedTaskId, setSelectedTaskId] = useState(null)
  const [taskDetails, setTaskDetails] = useState(null)
  const [activities, setActivities] = useState([])
  const [taskInput, setTaskInput] = useState('')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const loadTasks = useCallback(async () => {
    try {
      const response = await fetch(`${API}/tasks/`)
      if (!response.ok) throw new Error('Could not load tasks')

      const data = await response.json()
      setTasks(data)

      setSelectedTaskId((current) => {
        if (current && data.some((task) => task.task_id === current)) {
          return current
        }
        return data[0]?.task_id ?? null
      })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadTaskDetails = useCallback(async (taskId) => {
    if (!taskId) {
      setTaskDetails(null)
      setActivities([])
      return
    }

    try {
      const [taskResponse, activityResponse] = await Promise.all([
        fetch(`${API}/tasks/${taskId}`),
        fetch(`${API}/tasks/${taskId}/activities`),
      ])

      if (!taskResponse.ok) throw new Error('Could not load task details')
      if (!activityResponse.ok) throw new Error('Could not load activities')

      const [taskData, activityData] = await Promise.all([
        taskResponse.json(),
        activityResponse.json(),
      ])

      setTaskDetails(taskData)
      setActivities(activityData)
      setError('')
    } catch (err) {
      setError(err.message)
    }
  }, [])

  useEffect(() => {
    loadTasks()
    const interval = setInterval(loadTasks, 5000)
    return () => clearInterval(interval)
  }, [loadTasks])

  useEffect(() => {
    loadTaskDetails(selectedTaskId)
    if (!selectedTaskId) return

    const interval = setInterval(
      () => loadTaskDetails(selectedTaskId),
      3000,
    )
    return () => clearInterval(interval)
  }, [selectedTaskId, loadTaskDetails])

  async function submitTask(event) {
    event.preventDefault()

    const userTask = taskInput.trim()
    if (userTask.length < 5) {
      setError('Please enter a task with at least 5 characters.')
      return
    }

    setSubmitting(true)
    setError('')

    try {
      const response = await fetch(`${API}/tasks/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_task: userTask }),
      })

      if (!response.ok) {
        const body = await response.json()
        throw new Error(body.detail || 'Task submission failed')
      }

      const newTask = await response.json()
      setTaskInput('')
      setSelectedTaskId(newTask.task_id)
      await loadTasks()
      await loadTaskDetails(newTask.task_id)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const completedCount = tasks.filter(
    (task) => task.execution_status === 'completed',
  ).length

  const runningCount = tasks.filter(
    (task) => ['planning', 'executing', 'reviewing'].includes(
      task.execution_status,
    ),
  ).length

  const failedCount = tasks.filter(
    (task) => task.execution_status === 'failed',
  ).length

  const attemptHistory = buildAttemptHistory(activities)
  const actualRetryCount = Math.max(0, attemptHistory.length - 1)

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">A</div>
          <div>
            <strong>AI Workforce</strong>
            <span>Agent orchestration</span>
          </div>
        </div>

        <div className="sidebar-label">WORKSPACE</div>
        <button className="nav-item active">
          <span>▦</span> Overview
        </button>
        <button className="nav-item" onClick={() => document.getElementById('task-list')?.scrollIntoView({ behavior: 'smooth' })}>
          <span>☷</span> Tasks
        </button>
        <button className="nav-item" onClick={() => document.getElementById('activity-panel')?.scrollIntoView({ behavior: 'smooth' })}>
          <span>◷</span> Agent activity
        </button>

        <div className="sidebar-bottom">
          <div className="connection-indicator">
            <span className="online-dot" />
            Backend connected
          </div>
          <span className="sidebar-version">AI Workforce MVP · v0.1.0</span>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <div className="breadcrumb">Workspace / Overview</div>
            <h1>Dashboard</h1>
          </div>
          <div className="topbar-right">
            <span className="live-indicator"><span /> Live updates</span>
            <div className="avatar">U</div>
          </div>
        </header>

        <section className="welcome-section">
          <div>
            <p className="eyebrow">AI WORKFORCE CONTROL CENTER</p>
            <h2>Manage your AI agents</h2>
            <p className="welcome-copy">
              Submit tasks, monitor agent execution, and review results.
            </p>
          </div>
          <div className="welcome-decoration">✳</div>
        </section>

        {error && (
          <div className="error-banner" role="alert">
            {error}
            <button onClick={() => setError('')}>Dismiss</button>
          </div>
        )}

        <section className="stats-grid">
          <div className="stat-card">
            <span className="stat-label">Total tasks</span>
            <strong>{tasks.length}</strong>
            <span className="stat-footnote">All submitted tasks</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Completed</span>
            <strong>{completedCount}</strong>
            <span className="stat-footnote">Successfully approved</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">In progress</span>
            <strong>{runningCount}</strong>
            <span className="stat-footnote">Currently executing</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Failed</span>
            <strong>{failedCount}</strong>
            <span className="stat-footnote">Require attention</span>
          </div>
        </section>

        <section className="content-grid">
          <div className="panel submit-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">NEW WORKFLOW</p>
                <h3>Submit a task</h3>
              </div>
              <span className="panel-icon">✦</span>
            </div>
            <p className="panel-description">
              Give the Manager Agent a task. It will plan, delegate, execute,
              and review the result.
            </p>
            <form onSubmit={submitTask}>
              <label htmlFor="task-input">What should the agents do?</label>
              <textarea
                id="task-input"
                value={taskInput}
                onChange={(event) => setTaskInput(event.target.value)}
                placeholder="Example: Compare the top 5 AI customer support platforms..."
                rows={5}
                required
                minLength={5}
              />
              <div className="form-footer">
                <span>Manager Agent → Worker Agent → Review</span>
                <button type="submit" disabled={submitting}>
                  {submitting ? 'Submitting...' : 'Run task →'}
                </button>
              </div>
            </form>
          </div>

          <div className="panel selected-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">SELECTED TASK</p>
                <h3>Execution overview</h3>
              </div>
              {taskDetails && (
                <span className={`status-pill ${statusClass(taskDetails.execution_status)}`}>
                  {taskDetails.execution_status}
                </span>
              )}
            </div>

            {taskDetails ? (
              <>
                <p className="selected-task-text">{taskDetails.user_task}</p>
                <div className="detail-row">
                  <span>Task ID</span>
                  <code>{taskDetails.task_id}</code>
                </div>
                <div className="detail-row">
                  <span>Review</span>
                  <strong>{taskDetails.review_status || 'pending'}</strong>
                </div>
                <div className="detail-row">
                  <span>Retry attempts</span>
                  <strong>{taskDetails.retry_count ?? 0} / 2</strong>
                </div>
                <div className="detail-row">
                  <span>Created</span>
                  <strong>{formatDate(taskDetails.created_at)}</strong>
                </div>
              </>
            ) : (
              <div className="empty-state">
                {loading ? 'Loading tasks...' : 'Submit or select a task to see its details.'}
              </div>
            )}
          </div>
        </section>

        <section className="content-grid lower-grid">
          <div className="panel task-panel" id="task-list">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">WORK QUEUE</p>
                <h3>Recent tasks</h3>
              </div>
              <span className="count-label">{tasks.length} tasks</span>
            </div>

            {tasks.length === 0 ? (
              <div className="empty-state">
                {loading ? 'Loading tasks...' : 'No tasks yet. Submit your first task above.'}
              </div>
            ) : (
              <div className="task-list">
                {tasks.map((task) => (
                  <button
                    className={`task-item ${selectedTaskId === task.task_id ? 'selected' : ''}`}
                    key={task.task_id}
                    onClick={() => setSelectedTaskId(task.task_id)}
                  >
                    <span className="task-item-main">
                      <strong>{task.user_task}</strong>
                      <small>{formatDate(task.created_at)}</small>
                    </span>
                    <span className={`status-pill ${statusClass(task.execution_status)}`}>
                      {task.execution_status}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="panel activity-panel" id="activity-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">EXECUTION TRACE</p>
                <h3>Agent activity</h3>
              </div>
              <span className="count-label">{activities.length} events</span>
            </div>

            {activities.length === 0 ? (
              <div className="empty-state">
                Select a task to view its agent activity.
              </div>
            ) : (
              <div className="activity-list">
                {activities.map((activity) => (
                  <div className="activity-item" key={activity.id}>
                    <div className={`activity-marker ${statusClass(activity.status)}`} />
                    <div className="activity-content">
                      <div className="activity-title-row">
                        <strong>{activity.agent_name}</strong>
                        <span className={`activity-status ${statusClass(activity.status)}`}>
                          {activity.status}
                        </span>
                      </div>
                      <span className="activity-type">{activity.activity_type}</span>
                      <p>{activity.message}</p>
                      <time>{formatDate(activity.created_at)}</time>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

                <section className="panel retry-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">EXECUTION REVIEW</p>
              <h3>Retry history</h3>
            </div>
            <span className="count-label">
              {attemptHistory.length} execution attempts
            </span>
          </div>

          {attemptHistory.length === 0 ? (
            <div className="empty-state">
              Worker execution history will appear here.
            </div>
          ) : (
            <>
              <div className="detail-row">
                <span>Actual retries used</span>
                <strong>{actualRetryCount} / 2</strong>
              </div>

              <div className="retry-list">
                {attemptHistory.map((attempt) => (
                  <div className="retry-item" key={attempt.number}>
                    <div className="retry-item-heading">
                      <div>
                        <strong>Attempt {attempt.number}</strong>
                        <small>
                          {attempt.number === 1
                            ? 'Initial execution'
                            : `Retry ${attempt.number - 1}`}
                        </small>
                      </div>

                      <span className={`status-pill ${statusClass(attempt.reviewStatus)}`}>
                        {attempt.reviewStatus}
                      </span>
                    </div>

                    <p className="retry-description">
                      {attempt.reviewStatus === 'approved'
                        ? 'Manager approved the Worker output.'
                        : attempt.reviewStatus === 'rejected'
                          ? 'Manager rejected the Worker output.'
                          : 'Worker execution is awaiting review.'}
                    </p>

                    {attempt.feedback && (
                      <details className="retry-feedback">
                        <summary>View Manager feedback</summary>
                        <p>{attempt.feedback}</p>
                      </details>
                    )}

                    <small className="retry-time">
                      Started: {formatDate(attempt.startedAt)}
                    </small>
                  </div>
                ))}
              </div>

              {taskDetails?.execution_status === 'failed' && (
                <p className="retry-final-status">
                  Maximum of two retries reached. Task marked as failed.
                </p>
              )}
            </>
          )}
        </section>

<section className="panel output-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">DELIVERABLE</p>
              <h3>Final output</h3>
            </div>
            {taskDetails?.review_status && (
              <span className={`status-pill ${statusClass(taskDetails.review_status)}`}>
                {taskDetails.review_status}
              </span>
            )}
          </div>
          {taskDetails?.final_output ? (
            <div className="final-output markdown-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {taskDetails.final_output}
              </ReactMarkdown>
            </div>
          ) : (
            <div className="empty-state">
              The final result will appear here once the Manager Agent approves the output.
            </div>
          )}
        </section>

        <footer className="footer">
          AI Workforce · Multi-agent task orchestration platform
          <span>Powered by LangGraph + Gemini</span>
        </footer>
      </main>
    </div>
  )
}

export default App
