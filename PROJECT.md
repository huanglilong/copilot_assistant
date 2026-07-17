# Copilot Assistant - Project Summary

## Why

Monitor GitHub Copilot CLI session status in real-time from any device on the local network. Useful for tracking what Copilot is working on, how many sessions are active, token usage, and task progress — all from a phone or another computer.

## How

- **Collector** (`copilot_status/collector.py`): Reads Copilot CLI session data from `~/.copilot/session-state/` — workspace.yaml for metadata, events.jsonl for activity stream, session.db for todos, lock files for active session detection. Extracts last message, session status (working/waiting/error/idle), and event counts.
- **HTTP Server** (`copilot_status/server.py`): Flask server on port 8585 (dual-stack IPv4+IPv6) serving a dark-themed HTML dashboard with 5s auto-refresh and JSON API endpoints. Shows session status badges, last messages, and event statistics.
- **mDNS Broadcaster** (`copilot_status/mdns.py`): Registers `copilot.<username>.<hostname>.local` via Zeroconf. Uses `dns-sd` on macOS and `avahi-publish-service` on Linux for host .local resolution.
- **Entry Point** (`copilot_status/__main__.py`): CLI with argparse, signal handling, and graceful shutdown.

## Design Decisions

- **HTTP only** (no HTTPS): Browsers auto-attempt HTTPS on `.local` domains, but self-signed certs cause more issues than they solve. Use explicit `http://` prefix.
- **No send message**: Copilot CLI does not expose a local API for injecting messages into running sessions. The official remote control mechanism (`--remote`) routes through GitHub's cloud, not locally. TTY writing is unreliable (permissions, Ink framework input handling). Removed send feature to avoid broken UX.
- **Polling over WebSocket**: Simple 5s polling keeps the implementation lightweight. WebSocket/SSE can be added later for real-time push.

## TODOs

- [ ] Add token usage / cost tracking per session (if available in events)
- [ ] Add WebSocket/SSE support for real-time push updates instead of polling
- [ ] Add authentication for network access security
- [ ] Support multiple Copilot CLI installations / users
- [ ] Add historical session analytics (daily/weekly stats)
- [ ] Mobile-optimized dashboard layout improvements
- [ ] Add sound/notification on session completion or error
- [ ] Investigate `copilot --remote` + GitHub API for remote message sending
