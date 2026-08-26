import { useEffect, useState } from "react";
import {
  collection,
  query,
  orderBy,
  limit,
  onSnapshot,
} from "firebase/firestore";
import { db } from "./firebase.js";

const STATUS_STYLES = {
  queued: { label: "Queued", className: "status-queued" },
  starting: { label: "Starting", className: "status-starting" },
  running: { label: "Running", className: "status-running" },
  done: { label: "Done", className: "status-done" },
  no_changes: { label: "No changes", className: "status-no-changes" },
  failed: { label: "Failed", className: "status-failed" },
};

function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] ?? {
    label: status ?? "Unknown",
    className: "status-unknown",
  };
  return (
    <span className={`status-badge ${style.className}`}>{style.label}</span>
  );
}

function formatTime(ts) {
  if (!ts) return "\u2014";
  const date = ts.toDate ? ts.toDate() : new Date(ts);
  return date.toLocaleString();
}

function TaskRow({ task }) {
  return (
    <div className="task-row">
      <div className="task-row-top">
        <StatusBadge status={task.status} />
        <span className="task-time">{formatTime(task.created_at)}</span>
      </div>
      <div className="task-prompt">{task.prompt}</div>
      <div className="task-meta">
        {task.repo && <span className="task-repo">{task.repo}</span>}
        {task.from_whatsapp && (
          <span className="task-sender">
            {task.from_whatsapp.replace("whatsapp:", "")}
          </span>
        )}
      </div>
      {task.pr_url && (
        <a
          className="task-pr-link"
          href={task.pr_url}
          target="_blank"
          rel="noreferrer"
        >
          View pull request &rarr;
        </a>
      )}
      {task.error && <div className="task-error">{task.error}</div>}
    </div>
  );
}

export default function App() {
  const [tasks, setTasks] = useState(null); // null = loading, [] = loaded/empty
  const [error, setError] = useState(null);

  useEffect(() => {
    const q = query(
      collection(db, "tasks"),
      orderBy("created_at", "desc"),
      limit(50),
    );
    const unsubscribe = onSnapshot(
      q,
      (snapshot) => {
        setTasks(snapshot.docs.map((d) => ({ id: d.id, ...d.data() })));
        setError(null);
      },
      (err) => setError(err.message),
    );
    return unsubscribe;
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <h1>whatcode</h1>
        <span className="app-subtitle">Live task list</span>
      </header>

      {error && <div className="app-error">Couldn't load tasks: {error}</div>}
      {tasks === null && !error && (
        <div className="app-loading">Loading&hellip;</div>
      )}
      {tasks && tasks.length === 0 && (
        <div className="app-empty">
          No tasks yet. Send a message to get started.
        </div>
      )}

      <div className="task-list">
        {tasks?.map((task) => (
          <TaskRow key={task.id} task={task} />
        ))}
      </div>
    </div>
  );
}
