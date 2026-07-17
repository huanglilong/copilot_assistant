"""HTTP status server with HTML dashboard for Copilot CLI status."""

from flask import Flask, jsonify, render_template_string
from .collector import get_active_sessions, get_all_sessions, get_system_info

app = Flask(__name__)

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Copilot CLI Status</title>
<style>
  :root { --bg: #0d1117; --card: #161b22; --border: #30363d; --text: #c9d1d9; --dim: #8b949e; --accent: #58a6ff; --green: #3fb950; --yellow: #d29922; --red: #f85149; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); padding: 20px; }
  h1 { color: var(--accent); margin-bottom: 8px; font-size: 1.5em; }
  .subtitle { color: var(--dim); margin-bottom: 20px; font-size: 0.9em; }
  .system-info { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }
  .stat-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px 20px; min-width: 160px; }
  .stat-card .label { color: var(--dim); font-size: 0.8em; text-transform: uppercase; letter-spacing: 0.5px; }
  .stat-card .value { color: var(--text); font-size: 1.8em; font-weight: 700; margin-top: 4px; }
  .stat-card .value.active { color: var(--green); }
  .session-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 16px; }
  .session-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
  .session-name { font-size: 1.1em; font-weight: 600; color: var(--text); max-width: 70%; word-break: break-word; }
  .session-id { font-family: 'SF Mono', Menlo, monospace; font-size: 0.75em; color: var(--dim); margin-top: 4px; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.75em; font-weight: 600; }
  .badge-active { background: rgba(63,185,80,0.15); color: var(--green); border: 1px solid var(--green); }
  .badge-inactive { background: rgba(139,148,158,0.15); color: var(--dim); border: 1px solid var(--border); }
  .meta-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px 20px; margin-top: 12px; }
  .meta-item .meta-label { color: var(--dim); font-size: 0.75em; text-transform: uppercase; }
  .meta-item .meta-value { color: var(--text); font-size: 0.9em; margin-top: 2px; word-break: break-all; }
  .events-bar { display: flex; gap: 12px; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); flex-wrap: wrap; }
  .event-stat { font-size: 0.85em; }
  .event-stat .num { font-weight: 700; }
  .event-stat .num.user { color: var(--accent); }
  .event-stat .num.assistant { color: var(--green); }
  .event-stat .num.tool { color: var(--yellow); }
  .event-stat .num.error { color: var(--red); }
  .todos-list { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); }
  .todos-list h4 { color: var(--dim); font-size: 0.8em; text-transform: uppercase; margin-bottom: 8px; }
  .todo-item { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 0.85em; }
  .todo-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .todo-dot.pending { background: var(--dim); }
  .todo-dot.in_progress { background: var(--yellow); }
  .todo-dot.done { background: var(--green); }
  .todo-dot.blocked { background: var(--red); }
  .refresh-info { text-align: center; color: var(--dim); font-size: 0.8em; margin-top: 24px; }
  .all-sessions { margin-top: 32px; }
  .all-sessions h2 { color: var(--accent); font-size: 1.2em; margin-bottom: 12px; }
  .session-row { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; border-bottom: 1px solid var(--border); font-size: 0.85em; }
  .session-row:hover { background: rgba(88,166,255,0.05); }
  .session-row .name { max-width: 60%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
</head>
<body>
<h1>🤖 Copilot CLI Status</h1>
<p class="subtitle">Real-time status of GitHub Copilot CLI sessions on this machine</p>

<div class="system-info">
  <div class="stat-card">
    <div class="label">Active Sessions</div>
    <div class="value active" id="active-count">-</div>
  </div>
  <div class="stat-card">
    <div class="label">Total Sessions</div>
    <div class="value" id="total-count">-</div>
  </div>
  <div class="stat-card">
    <div class="label">Last Updated</div>
    <div class="value" style="font-size:0.9em;" id="updated-at">-</div>
  </div>
</div>

<h2 style="color:var(--accent);font-size:1.2em;margin-bottom:12px;">Active Sessions</h2>
<div id="active-sessions"></div>

<div class="all-sessions">
  <h2>Recent Sessions</h2>
  <div id="all-sessions"></div>
</div>

<div class="refresh-info">Auto-refresh every 5 seconds &bull; <a href="/api/status" style="color:var(--accent);">JSON API</a></div>

<script>
function renderBadge(active) {
  return active
    ? '<span class="badge badge-active">● Active</span>'
    : '<span class="badge badge-inactive">○ Inactive</span>';
}

function renderTodos(todos) {
  if (!todos || todos.length === 0) return '';
  let html = '<div class="todos-list"><h4>Todos</h4>';
  todos.forEach(t => {
    html += '<div class="todo-item"><span class="todo-dot ' + t.status + '"></span>' +
            '<span>' + escapeHtml(t.title) + ' <span style="color:var(--dim)">(' + t.status + ')</span></span></div>';
  });
  html += '</div>';
  return html;
}

function escapeHtml(text) {
  const d = document.createElement('div');
  d.textContent = text;
  return d.innerHTML;
}

function renderActiveSessions(sessions) {
  const el = document.getElementById('active-sessions');
  if (!sessions.length) {
    el.innerHTML = '<p style="color:var(--dim)">No active sessions</p>';
    return;
  }
  el.innerHTML = sessions.map(s => {
    const ws = s.workspace || {};
    const ev = s.events_summary || {};
    const lastAct = ev.last_activity ? new Date(ev.last_activity).toLocaleString() : 'N/A';
    return '<div class="session-card">' +
      '<div class="session-header">' +
        '<div><div class="session-name">' + escapeHtml(ws.name || 'Unnamed Session') + '</div>' +
        '<div class="session-id">' + s.session_id + '</div></div>' +
        renderBadge(true) +
      '</div>' +
      '<div class="meta-grid">' +
        '<div class="meta-item"><div class="meta-label">Working Dir</div><div class="meta-value">' + escapeHtml(ws.cwd || '-') + '</div></div>' +
        '<div class="meta-item"><div class="meta-label">Branch</div><div class="meta-value">' + escapeHtml(ws.branch || '-') + '</div></div>' +
        '<div class="meta-item"><div class="meta-label">Model</div><div class="meta-value">' + escapeHtml(ev.model || '-') + '</div></div>' +
        '<div class="meta-item"><div class="meta-label">Version</div><div class="meta-value">' + escapeHtml(ev.copilot_version || '-') + '</div></div>' +
        '<div class="meta-item"><div class="meta-label">PID</div><div class="meta-value">' + s.pid + '</div></div>' +
        '<div class="meta-item"><div class="meta-label">Last Activity</div><div class="meta-value">' + lastAct + '</div></div>' +
      '</div>' +
      '<div class="events-bar">' +
        '<span class="event-stat">💬 User: <span class="num user">' + ev.user_messages + '</span></span>' +
        '<span class="event-stat">🤖 Assistant: <span class="num assistant">' + ev.assistant_messages + '</span></span>' +
        '<span class="event-stat">🔧 Tools: <span class="num tool">' + ev.tool_calls + '</span></span>' +
        '<span class="event-stat">❌ Errors: <span class="num error">' + ev.errors + '</span></span>' +
        '<span class="event-stat">📊 Total Events: <span class="num">' + ev.total_events + '</span></span>' +
      '</div>' +
      renderTodos(s.todos) +
    '</div>';
  }).join('');
}

function renderAllSessions(sessions) {
  const el = document.getElementById('all-sessions');
  el.innerHTML = sessions.map(s => {
    const ws = s.workspace || {};
    const updated = ws.updated_at ? new Date(ws.updated_at).toLocaleString() : '-';
    return '<div class="session-row">' +
      '<span class="name">' + escapeHtml(ws.name || s.session_id) + '</span>' +
      '<span style="display:flex;align-items:center;gap:8px;">' +
        renderBadge(s.active) +
        '<span style="color:var(--dim);font-size:0.8em;">' + updated + '</span>' +
      '</span>' +
    '</div>';
  }).join('');
}

async function refresh() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    document.getElementById('active-count').textContent = data.system.active_session_count;
    document.getElementById('total-count').textContent = data.system.total_session_count;
    document.getElementById('updated-at').textContent = new Date(data.system.collected_at).toLocaleString();
    renderActiveSessions(data.active_sessions || []);
    renderAllSessions(data.all_sessions || []);
  } catch (e) {
    console.error('Refresh failed:', e);
  }
}

refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>"""


@app.route("/")
def dashboard():
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/status")
def api_status():
    return jsonify({
        "system": get_system_info(),
        "active_sessions": get_active_sessions(),
        "all_sessions": get_all_sessions(),
    })


@app.route("/api/sessions/active")
def api_active_sessions():
    return jsonify(get_active_sessions())


@app.route("/api/sessions")
def api_all_sessions():
    return jsonify(get_all_sessions())


@app.route("/health")
def health():
    return jsonify({"status": "ok"})
