# Repository Guidelines

## Project Overview
Kyoto City Bus route search LINE bot. Users send departure/destination stops and receive bus route info as Flex Messages.

- **Stack**: Python 3.12.3, Flask 3.1.3, line-bot-sdk 3.26.0
- **Port**: 8083 in production (`FLASK_PORT` in `.env`, systemd managed); the code default is 8000
- **External API**: [kcb_api](https://github.com/kmch4n/kcb_api) at `localhost:8081/kcb_api`, authenticated with `X-API-Key`

## Project Structure & Module Organization
- `main.py`: Flask webhook entry point for LINE callbacks (signature verification).
- `config.py`: Environment loading, LINE SDK setup, and `API_BASE_URL` / `FLASK_PORT` defaults.
- `handlers.py`: LINE message handlers and orchestration.
- `message_parser.py`: User input parsing and command detection.
- `session.py`: In-memory session state (10-minute timeout).
- `bus_api.py`: Kyoto City Bus API client and timetable-based bus position helpers.
- `storage.py`: Search history and favorites persistence (fcntl-locked JSON in `data/`).
- `flex_templates.py`: Flex Message JSON builders.
- `data/`: Runtime data (e.g., `data/search_history.json`); gitignored.
- `notes/`: Internal review notes; gitignored.
- `docs/deployment.md`: Setup and deployment guide.

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

## Build, Test, and Development Commands
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
```bash
python3 main.py
```
Runs the webhook server (default `http://localhost:8000`, override via `FLASK_PORT` in `.env`).

Service management and sanity checks:
```bash
systemctl restart kcb_linebot.service
journalctl -u kcb_linebot.service -f
curl http://localhost:8083/kcb_linebot/health
```

## Key Design Decisions
- **Sessions are in-memory**: an intentional tradeoff for simplicity. They are lost on restart and do not scale horizontally.
- **Storage uses fcntl file locking** on `data/search_history.json` for concurrent access safety. Favorites are capped at 5 per user (`MAX_FAVORITES`).
- **Bus position is estimated from the timetable**, not GPS. `bus_api.get_trip_location()` returns how many stops away the bus is, and the Flex Message shows it as "departed N stops before", "stopped N stops before", or "still far away".
- **Late-night handling**: from 21:00 to 05:00, a search with no results falls back to the next day's first bus.
- **QuickReply strategy varies by context**:
  - Default: Help + top favorites
  - Search results: + reverse search button
  - Session active: + cancel option
  - Location message: nearby stops list
- **Route color coding** by number (Material Design): 1-19 green, 20-39 blue, 40-59 orange, 60-79 purple, 80+ red.
- **All user-facing messages are in Japanese**; code and logs are in English.

## Coding Style & Naming Conventions
- Indentation: 4 spaces, no tabs.
- Python: follow PEP 8; prefer type hints and short, focused functions.
- Docstrings: required for public functions (Google-style preferred).
- Logging: use `logging.getLogger(__name__)` and structured messages.

## Testing Guidelines
- Automated tests are not yet present.
- If adding tests, use `pytest` and place files under `tests/` (e.g., `tests/test_message_parser.py`).
- Use descriptive test names for intent clarity (e.g., `test_parse_bus_search_message_with_arrow`).

## Commit & Pull Request Guidelines
- Commit message format: `[emoji] English commit message` following gitmoji standards.
  - Examples: `[🐛] Fix duplicate route display`, `[📝] Update README`.
- Do not run `git add/commit/push` automatically; the user handles Git operations.
- PRs should include: summary, linked issue (if any), and test notes.

## Security & Configuration Tips
- Configure secrets in `.env`; never commit `.env`.
- The LINE webhook endpoint is `/kcb_linebot/callback`.

| Variable | Required | Default |
|----------|----------|---------|
| `LINE_CHANNEL_ACCESS_TOKEN` | Yes | — |
| `LINE_CHANNEL_SECRET` | Yes | — |
| `API_KEY` | Yes (Bus API auth) | — |
| `API_BASE_URL` | No | `http://localhost:8081/kcb_api` |
| `FLASK_PORT` | No | `8000` |
| `FLASK_DEBUG` | No | `False` |

## Known Tech Debt
- `format_time()` is duplicated in `handlers.py` and `flex_templates.py`.
- `API_BASE_URL` has a hardcoded fallback in `config.py` (should be env-var only).
- Logging goes to stdout only (no file rotation configured).
