# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kyoto City Bus route search LINE bot. Users send departure/destination stops and receive bus route info as Flex Messages.

- **Stack**: Python 3.12.3, Flask 3.0.0, line-bot-sdk 3.21.0
- **Port**: 8083 (systemd managed)
- **External API**: Kyoto Bus API at `localhost:8081/kcb_api`

## Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# Run
python3 main.py

# Service management
systemctl restart kcb_linebot.service
journalctl -u kcb_linebot.service -f

# Health check
curl http://localhost:8083/kcb_linebot/health
```

No automated tests exist yet. Use pytest under `tests/` if adding tests.

## Architecture

```
LINE Webhook POST /kcb_linebot/callback
  → main.py          (Flask server, signature verification)
  → handlers.py      (message routing & orchestration)
    → message_parser.py  (parse user intent: search, commands, favorites)
    → session.py         (in-memory session state, 10min timeout)
    → bus_api.py         (Kyoto Bus API client, X-API-Key auth)
    → storage.py         (fcntl-locked JSON persistence in data/)
    → flex_templates.py  (Flex Message UI builders)
  → LINE Reply (TextMessage / FlexMessage with QuickReply)
```

## Key Design Decisions

- **Sessions are in-memory** — intentional tradeoff for simplicity. Lost on restart, not horizontally scalable.
- **Storage uses fcntl file locking** on `data/search_history.json` for concurrent access safety. Favorites capped at 5 per user.
- **Realtime info is timetable-based estimation**, not GPS. Shows "approaching" (0-3min), "on time" (4-10min), nothing if >10min.
- **Late-night handling**: after 21:00 with no results, searches next day's first bus.
- **QuickReply strategy varies by context**:
  - Default: Help + Top favorites
  - Search results: + Reverse search button
  - Session active: + Cancel option
  - Location message: Nearby stops list
- **Route color coding** by number (Material Design): 1-19 green, 20-39 blue, 40-59 orange, 60-79 purple, 80+ red.
- **All user-facing messages in Japanese**, code and logs in English.

## Coding Conventions

- **Git policy**: Never auto-commit/push — user handles all git operations
- **Python**: PEP 8, type hints, Google-style docstrings, `logging.getLogger(__name__)`

## Environment Variables (.env)

```
LINE_CHANNEL_ACCESS_TOKEN  # Required
LINE_CHANNEL_SECRET        # Required
API_KEY                    # Required (Bus API auth)
FLASK_PORT                 # Optional (default: 8000)
FLASK_DEBUG                # Optional (default: False)
```

## Known Tech Debt

- `format_time()` duplicated in `handlers.py` and `flex_templates.py`
- `API_BASE_URL` has hardcoded fallback in `bus_api.py` (should be env-var only)
- Logging to stdout only (no file rotation configured)
- Several unused functions marked for future phases (see docstrings)
