"""HTTP status server with HTML dashboard for Copilot CLI status."""

import logging

from flask import Flask, jsonify, Response
from .collector import get_active_sessions, get_all_sessions, get_system_info

logger = logging.getLogger(__name__)

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
  .badge-waiting { background: rgba(210,153,34,0.15); color: var(--yellow); border: 1px solid var(--yellow); }
  .badge-working { background: rgba(88,166,255,0.15); color: var(--accent); border: 1px solid var(--accent); }
  .badge-error { background: rgba(248,81,73,0.15); color: var(--red); border: 1px solid var(--red); }
  .badge-idle { background: rgba(139,148,158,0.15); color: var(--dim); border: 1px solid var(--border); }
  .status-section { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); }
  .last-message { background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: 10px 12px; font-size: 0.85em; color: var(--text); max-height: 120px; overflow-y: auto; white-space: pre-wrap; word-break: break-word; line-height: 1.5; }
  .last-message.user-msg { border-left: 3px solid var(--accent); }
  .last-message.assistant-msg { border-left: 3px solid var(--green); }
  .last-message.tool-msg { border-left: 3px solid var(--yellow); }
  .msg-label { font-size: 0.75em; color: var(--dim); margin-bottom: 4px; text-transform: uppercase; }
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

<div class="refresh-info">Auto-refresh every 5 seconds &bull; <a href="/api/status" style="color:var(--accent);">JSON API</a> <span id="refresh-error" style="color:var(--red);"></span></div>

<script>
function escapeHtml(text) {
  var d = document.createElement('div');
  d.textContent = text;
  return d.innerHTML;
}

function renderBadge(active) {
  return active
    ? '<span class="badge badge-active">● Active</span>'
    : '<span class="badge badge-inactive">○ Inactive</span>';
}

function renderTodos(todos) {
  if (!todos || todos.length === 0) return '';
  var html = '<div class="todos-list"><h4>Todos</h4>';
  todos.forEach(function(t) {
    html += '<div class="todo-item"><span class="todo-dot ' + escapeHtml(t.status) + '"></span>' +
            '<span>' + escapeHtml(t.title) + ' <span style="color:var(--dim)">(' + escapeHtml(t.status) + ')</span></span></div>';
  });
  html += '</div>';
  return html;
}

function renderStatusBadge(status) {
  var map = {
    'working': '<span class="badge badge-working">⚡ Working</span>',
    'waiting': '<span class="badge badge-waiting">⏳ Waiting for input</span>',
    'error': '<span class="badge badge-error">❌ Error</span>',
    'idle': '<span class="badge badge-idle">○ Idle</span>'
  };
  return map[status] || map['idle'];
}

function renderLastMessage(ev) {
  if (!ev.last_message) return '';
  var typeClass = ev.last_message_type === 'user' ? 'user-msg' :
                  ev.last_message_type === 'assistant' ? 'assistant-msg' : 'tool-msg';
  var typeLabel = ev.last_message_type === 'user' ? '👤 User' :
                  ev.last_message_type === 'assistant' ? '🤖 Assistant' : '🔧 Tool';
  return '<div class="msg-label">' + typeLabel + (ev.last_tool ? ' → ' + escapeHtml(ev.last_tool) : '') + '</div>' +
         '<div class="last-message ' + typeClass + '">' + escapeHtml(ev.last_message) + '</div>';
}

function renderActiveSessions(sessions) {
  var el = document.getElementById('active-sessions');
  if (!sessions.length) {
    el.innerHTML = '<p style="color:var(--dim)">No active sessions</p>';
    return;
  }
  el.innerHTML = sessions.map(function(s) {
    var ws = s.workspace || {};
    var ev = s.events_summary || {};
    var lastAct = ev.last_activity ? new Date(ev.last_activity).toLocaleString() : 'N/A';
    var sid = s.session_id;
    var status = ev.status || 'idle';
    return '<div class="session-card" data-sid="' + escapeHtml(sid) + '">' +
      '<div class="session-header">' +
        '<div><div class="session-name">' + escapeHtml(ws.name || 'Unnamed Session') + '</div>' +
        '<div class="session-id">' + escapeHtml(sid) + '</div></div>' +
        renderStatusBadge(status) +
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
      '<div class="status-section">' +
        renderLastMessage(ev) +
      '</div>' +
      renderTodos(s.todos) +
    '</div>';
  }).join('');
}

function renderAllSessions(sessions) {
  var el = document.getElementById('all-sessions');
  el.innerHTML = sessions.map(function(s) {
    var ws = s.workspace || {};
    var updated = ws.updated_at ? new Date(ws.updated_at).toLocaleString() : '-';
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
    var res = await fetch('/api/status');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    var data = await res.json();
    if (data.error) throw new Error(data.error);
    document.getElementById('active-count').textContent = data.system.active_session_count;
    document.getElementById('total-count').textContent = data.system.total_session_count;
    document.getElementById('updated-at').textContent = new Date(data.system.collected_at).toLocaleString();
    renderActiveSessions(data.active_sessions || []);
    renderAllSessions(data.all_sessions || []);
    document.getElementById('refresh-error').textContent = '';
  } catch (e) {
    console.error('Refresh failed:', e);
    document.getElementById('refresh-error').textContent = '⚠ Refresh failed: ' + e.message;
  }
}

refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>"""


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


@app.route("/")
def dashboard():
    return Response(DASHBOARD_HTML, mimetype="text/html", headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    })


@app.route("/api/status")
def api_status():
    try:
        return jsonify({
            "system": get_system_info(),
            "active_sessions": get_active_sessions(),
            "all_sessions": get_all_sessions(),
        })
    except Exception as e:
        logger.error("API /api/status error: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/sessions/active")
def api_active_sessions():
    try:
        return jsonify(get_active_sessions())
    except Exception as e:
        logger.error("API /api/sessions/active error: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/sessions")
def api_all_sessions():
    try:
        return jsonify(get_all_sessions())
    except Exception as e:
        logger.error("API /api/sessions error: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok"})
