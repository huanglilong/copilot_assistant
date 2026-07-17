# Copilot Assistant - Project Summary

## Why

Monitor GitHub Copilot CLI session status in real-time from any device on the local network. Useful for tracking what Copilot is working on, how many sessions are active, token usage, and task progress — all from a phone or another computer.

## How

- **Collector** (`copilot_status/collector.py`): Reads Copilot CLI session data from `~/.copilot/session-state/` — workspace.yaml for metadata, events.jsonl for activity stream, session.db for todos, lock files for active session detection.
- **HTTP Server** (`copilot_status/server.py`): Flask server on port 8585 (dual-stack IPv4+IPv6) serving a dark-themed HTML dashboard with 5s auto-refresh and JSON API endpoints.
- **mDNS Broadcaster** (`copilot_status/mdns.py`): Registers `copilot.<username>.<hostname>.local` via Zeroconf. Uses `dns-sd` on macOS and `avahi-publish-service` on Linux for host .local resolution.
- **Entry Point** (`copilot_status/__main__.py`): CLI with argparse, signal handling, and graceful shutdown.

## TODOs

- [ ] Add HTTPS support with self-signed cert (browsers auto-attempt HTTPS on .local)
- [ ] Add token usage / cost tracking per session (if available in events)
- [ ] Add WebSocket support for real-time push updates instead of polling
- [ ] Add authentication for network access security
- [ ] Support multiple Copilot CLI installations / users
- [ ] Add historical session analytics (daily/weekly stats)
- [ ] Mobile-optimized dashboard layout improvements
- [ ] Add sound/notification on session completion or error
