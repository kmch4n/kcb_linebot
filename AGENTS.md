# Repository Guidelines

## Project Structure & Module Organization
- `main.py`: Flask webhook entry point for LINE callbacks.
- `handlers.py`: LINE message handlers and orchestration.
- `bus_api.py`: Kyoto City Bus API client and realtime helpers.
- `flex_templates.py`: Flex Message JSON builders.
- `message_parser.py`: User input parsing and command detection.
- `session.py`: In-memory session state.
- `storage.py`: Search history and favorites persistence (JSON in `data/`).
- `data/`: Runtime data (e.g., `data/search_history.json`); not intended for Git commits.
- `notes/`: Internal review notes.

## Build, Test, and Development Commands
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
```bash
python3 main.py
```
Runs the webhook server (default `http://localhost:8000`, override via `.env`).

Optional sanity checks:
```bash
curl http://localhost:8083/kcb_linebot/health
```

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
- Configure secrets in `.env` (LINE tokens and API key); never commit `.env`.
- `API_BASE_URL` defaults to `http://localhost:8081/kcb_api`; override in `.env`.
- The LINE webhook endpoint is `/kcb_linebot/callback`.
