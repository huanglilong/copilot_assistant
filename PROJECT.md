# Copilot Assistant - Project Summary

## Why

Monitor GitHub Copilot CLI session status in real-time from any device on the local network. Useful for tracking what Copilot is working on, how many sessions are active, token usage, and task progress — all from a phone or another computer.

## How

- **Collector** (`copilot_status/collector.py`): Reads Copilot CLI session data from `~/.copilot/session-state/` — workspace.yaml for metadata, events.jsonl for activity stream, session.db for todos, lock files for active session detection. Single-pass events.jsonl parsing extracts last message, session status (working/waiting/error/idle), and event counts. Validates PID from lock filenames.
- **HTTP Server** (`copilot_status/server.py`): Flask server on port 8585 (dual-stack IPv4+IPv6) serving a dark-themed HTML dashboard with 5s auto-refresh and JSON API endpoints. Shows session status badges, last messages, and event statistics. Includes CORS headers, API error handling, and dashboard error indicators.
- **mDNS Broadcaster** (`copilot_status/mdns.py`): Registers `copilot.<username>.<hostname>.local` via Zeroconf. Uses `dns-sd` on macOS and `avahi-publish-address`/`avahi-publish-service` on Linux for host .local resolution. Auto-detects `mdns4_minimal` misconfiguration and logs fix instructions. Socket resource safety with try/finally.
- **Sender** (`copilot_status/sender.py`): TTY-based and `copilot -p` fallback message sender. Reserved for future `--remote` integration; not wired to the UI yet.
- **Entry Point** (`copilot_status/__main__.py`): CLI with argparse, signal handling, and graceful shutdown.

## Design Decisions

- **HTTP only** (no HTTPS): Browsers auto-attempt HTTPS on `.local` domains, but self-signed certs cause more issues than they solve. Use explicit `http://` prefix.
- **No send message (yet)**: Copilot CLI does not expose a local API for injecting messages into running sessions. The official remote control mechanism (`--remote`) routes through GitHub's cloud, not locally. TTY writing is unreliable (permissions, Ink framework input handling). Sender module kept for future `--remote` integration.
- **Polling over WebSocket**: Simple 5s polling keeps the implementation lightweight. WebSocket/SSE can be added later for real-time push.
- **Single-pass events parsing**: `_read_events_summary()` handles both event counting and waiting-status detection in one file read, avoiding the old duplicated `_check_waiting()` scan.
- **API error handling**: All API endpoints catch exceptions and return JSON error responses (500) instead of crashing. Dashboard shows a red error indicator on refresh failure.
- **CORS enabled**: `Access-Control-Allow-Origin: *` on all responses so external frontends can consume the API.

## Linux mDNS Notes

- **`avahi-publish-address`** (A record registration) is preferred for multi-label `.local` hostname resolution but returns "Not supported" on some distros. The app falls back to `avahi-publish-service` (DNS-SD only) and logs the IP for direct access.
- **`mdns4_minimal`** in nsswitch.conf only resolves single-label `.local` names. Multi-label names like `copilot.user.host.local` require `mdns4`. The app auto-detects this and logs a warning with the fix command.

## TODOs

- [ ] Add token usage / cost tracking per session (if available in events)
- [ ] Add WebSocket/SSE support for real-time push updates instead of polling
- [ ] Add authentication for network access security
- [ ] Support multiple Copilot CLI installations / users
- [ ] Add historical session analytics (daily/weekly stats)
- [ ] Mobile-optimized dashboard layout improvements
- [ ] Add sound/notification on session completion or error
- [ ] Investigate `copilot --remote` + GitHub API for remote message sending
