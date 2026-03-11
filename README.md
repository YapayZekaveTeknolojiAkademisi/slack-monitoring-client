# Slack Monitoring System

A production-ready Slack event listener that receives workspace events over Socket Mode, normalizes them into a standard payload format, and enqueues them for downstream consumers. Built for reliability: structured logging, graceful shutdown, and error handling that keeps the process running on event-level failures.

---

## Features

- **Slack Socket Mode** — No public URL or ngrok; connects to Slack via WebSocket using an app-level token.
- **Event coverage** — Messages, reactions, channel lifecycle, user presence, file activity, and more (30+ event types).
- **Shared queue** — Events are pushed to a multiprocessing queue (`QueueServer`) so other processes can consume them.
- **Structured logging** — Three rotating log files: system (INFO), errors (JSON), and queue events.
- **Graceful shutdown** — SIGINT/SIGTERM trigger clean teardown: Socket Mode disconnect, queue shutdown, log flush.
- **Error resilience** — Event-handling errors are logged and answered with 200 so Slack does not retry indefinitely; the process keeps running.

---

## Requirements

- Python 3.10+
- A Slack app with Socket Mode enabled and an **App-Level Token** (e.g. `xapp-...`) with `connections:write`.
- Required scopes/subscriptions depend on the events you use (e.g. `message`, `reaction_added`, `member_joined_channel`).

---

## Installation

```bash
git clone <repository-url>
cd slack-monitoring-system
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Configuration

Copy the example env file and set your values:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|----------|----------|-------------|
| `SLACK_APP_TOKEN` | Yes | Slack App-Level Token (`xapp-...`). |
| `QUEUE_HOST` | No | Queue manager bind address (default: `127.0.0.1`). |
| `QUEUE_PORT` | No | Queue manager port (default: `50000`). |
| `QUEUE_AUTHKEY` | No* | Secret for queue manager auth. *Required in production: set `ENV=production` and a strong value. |
| `LOG_DIR` | No | Directory for log files (default: `logs`). |
| `ENV` | No | Set to `production` to enforce a non-default `QUEUE_AUTHKEY`. |

---

## Usage

**Run in foreground (development):**

```bash
export PYTHONPATH=.
python -m src.main
```

**Run in background (start/stop scripts):**

```bash
./start.sh   # Starts the process and writes PID to .pid
./stop.sh    # Sends SIGTERM, then SIGKILL if needed
```

Stop with `Ctrl+C` when running in the foreground; shutdown is graceful.

---

## Logging

All logs go under `LOG_DIR` (default: `logs/`). One logger is used across the app (`app`).

| File | Content | Format |
|------|---------|--------|
| `system.log` | Startup, lifecycle, and general INFO messages. | Plain text: `timestamp \| level \| message` |
| `error.log` | ERROR and above only. | JSON (timestamp, level, message, exception if any) |
| `queue.log` | Records that carry a `queue_event` (enqueued events). | Human-readable with event_type, user_id, channel_id, etc. |

Log level is INFO; DEBUG is not written. Rotation: 10 MB per file, 5 backups.

---

## Queue payload format

Events are normalized to a common dict before being put on the queue:

- **Required:** `event_type` (string).
- **Common:** `user_id`, `channel_id`, `ts`, `thread_ts`, `text` (optional).
- **Event-specific:** e.g. `reaction`, `links`, `file_id`, `channel_name`.

Consumers should expect `dict[str, Any]` with at least `event_type`; other keys depend on the event type.

---

## Production

1. Set `ENV=production` and a strong `QUEUE_AUTHKEY` in `.env` (otherwise the app refuses to start).
2. Run behind a process manager (e.g. systemd, supervisord, or Docker with a restart policy) so the process is restarted if it exits.
3. Use `./start.sh` / `./stop.sh` or equivalent; ensure `LOG_DIR` is writable and has enough disk space for rotating logs.

---

## Project layout

```
.
├── src/
│   ├── main.py          # Entry point: start(), stop(), signal handling
│   ├── listener.py      # Bolt app, Socket Mode, event handlers, _enqueue()
│   ├── queue.py         # QueueServer, build_message_event(), shared queue
│   └── core/
│       ├── logger.py    # Logging config, formatters, filters
│       ├── settings.py  # Pydantic settings from .env
│       └── singleton.py # Singleton metaclass for QueueServer
├── logs/                # system.log, error.log, queue.log (created at runtime)
├── .env.example
├── requirements.txt
├── start.sh
├── stop.sh
└── README.md
```

---