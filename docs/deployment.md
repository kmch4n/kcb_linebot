# Deployment Guide

A step-by-step guide for setting up and deploying the Kyoto City Bus LINE Bot.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Tech Stack](#tech-stack)
- [Step 1: Set Up the Bus API](#step-1-set-up-the-bus-api)
- [Step 2: Create a LINE Bot Account](#step-2-create-a-line-bot-account)
- [Step 3: Install the Bot](#step-3-install-the-bot)
- [Step 4: Configure Environment Variables](#step-4-configure-environment-variables)
- [Step 5: Run the Server](#step-5-run-the-server)
- [Step 6: Configure the LINE Webhook](#step-6-configure-the-line-webhook)
- [Step 7: Verify Everything Works](#step-7-verify-everything-works)
- [Running as a Systemd Service](#running-as-a-systemd-service)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)

## Prerequisites

Before you begin, make sure you have the following:

- **Python 3.12+** installed on your server
- **A running instance of [kcb_api](https://github.com/kmch4n/kcb_api)** — This bot depends on the Kyoto City Bus API for all route and timetable data. Set it up first.
- **A LINE Developers account** — Sign up at [developers.line.biz](https://developers.line.biz/)
- **A public-facing server with HTTPS** — LINE requires a webhook URL with a valid SSL certificate. You can use a reverse proxy like Nginx or a tunneling tool like ngrok for development.

## Tech Stack

| Component | Version |
|---|---|
| Python | 3.12+ |
| Flask | 3.0.0 |
| line-bot-sdk | 3.21.0 |
| python-dotenv | 1.0.0 |
| requests | 2.31.0+ |

## Step 1: Set Up the Bus API

The bot calls the Kyoto City Bus API (kcb_api) for all route searches, stop lookups, and timetable data.

1. Follow the setup instructions at [github.com/kmch4n/kcb_api](https://github.com/kmch4n/kcb_api)
2. Ensure the API is running and accessible (default: `http://localhost:8081/kcb_api`)
3. Note your API key — you'll need it in Step 4

You can verify the API is running:

```bash
curl http://localhost:8081/kcb_api/health
```

## Step 2: Create a LINE Bot Account

1. Go to the [LINE Developers Console](https://developers.line.biz/console/)
2. Create a new **Provider** (or select an existing one)
3. Create a new **Messaging API Channel**
4. On the channel settings page, note the following credentials:
   - **Channel secret** (under "Basic settings")
   - **Channel access token** — click "Issue" to generate one (under "Messaging API")
5. Under "Messaging API" settings:
   - Disable **Auto-reply messages** (the bot handles all replies)
   - Disable **Greeting messages** (optional)

## Step 3: Install the Bot

Clone the repository and set up a Python virtual environment:

```bash
git clone https://github.com/kmch4n/kcb_linebot.git
cd kcb_linebot
```

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Step 4: Configure Environment Variables

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your values:

```bash
# LINE Messaging API (Required)
# Get these from the LINE Developers Console (Step 2)
LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token_here
LINE_CHANNEL_SECRET=your_channel_secret_here

# Kyoto City Bus API (Required)
# The API key for authenticating with kcb_api
API_KEY=your_kcb_api_key_here
API_BASE_URL=http://localhost:8081/kcb_api

# Server Configuration (Optional)
FLASK_PORT=8083
FLASK_DEBUG=False
```

### Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `LINE_CHANNEL_ACCESS_TOKEN` | Yes | — | LINE Messaging API long-lived token |
| `LINE_CHANNEL_SECRET` | Yes | — | LINE channel secret for signature verification |
| `API_KEY` | Yes | — | Authentication key for the Kyoto Bus API |
| `API_BASE_URL` | No | `http://localhost:8081/kcb_api` | Base URL of the kcb_api instance |
| `FLASK_PORT` | No | `8000` | Port the Flask server listens on |
| `FLASK_DEBUG` | No | `False` | Enable Flask debug mode (do not use in production) |

> **Note:** The server will exit immediately if `LINE_CHANNEL_ACCESS_TOKEN` or `LINE_CHANNEL_SECRET` is not set.

## Step 5: Run the Server

```bash
source .venv/bin/activate
python3 main.py
```

You should see output like:

```
Starting KCB LINE Bot webhook server...
Port: 8083, Debug: False
 * Running on http://0.0.0.0:8083
```

## Step 6: Configure the LINE Webhook

1. Go to your channel in the [LINE Developers Console](https://developers.line.biz/console/)
2. Navigate to **Messaging API** settings
3. Set the **Webhook URL** to:
   ```
   https://your-domain.com/kcb_linebot/callback
   ```
4. Click **Verify** — it should return a success response
5. Enable **Use webhook**

> **Important:** The URL must use HTTPS. For local development, use a tunneling tool like [ngrok](https://ngrok.com/):
> ```bash
> ngrok http 8083
> ```
> Then use the ngrok HTTPS URL as your webhook URL.

## Step 7: Verify Everything Works

1. **Health check** — Confirm the server is running:
   ```bash
   curl http://localhost:8083/kcb_linebot/health
   ```
   Expected response:
   ```json
   {"status": "ok", "service": "kcb_linebot", "timestamp": "..."}
   ```

2. **LINE test** — Open your LINE app, add the bot as a friend, and send:
   ```
   京都駅前 四条河原町
   ```
   You should receive a Flex Message with bus route information.

3. **Help command** — Send `ヘルプ` to verify the bot responds with usage instructions.

## Running as a Systemd Service

For production, run the bot as a systemd service so it starts automatically and restarts on failure.

Create a service file at `/etc/systemd/system/kcb_linebot.service`:

```ini
[Unit]
Description=Kyoto City Bus LINE Bot
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/kcb_linebot
ExecStart=/path/to/kcb_linebot/.venv/bin/python3 main.py
Restart=on-failure
RestartSec=5
EnvironmentFile=/path/to/kcb_linebot/.env

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable kcb_linebot.service
sudo systemctl start kcb_linebot.service
```

Common management commands:

```bash
# Check status
systemctl status kcb_linebot.service

# Restart after code changes
sudo systemctl restart kcb_linebot.service

# View live logs
journalctl -u kcb_linebot.service -f

# View recent logs (last 100 lines)
journalctl -u kcb_linebot.service -n 100
```

## Project Structure

```
kcb_linebot/
├── main.py               # Flask server — webhook endpoint & health check
├── config.py             # Environment variable loading & LINE SDK init
├── handlers.py           # Message routing — dispatches to appropriate handler
├── bus_api.py            # HTTP client for kcb_api (route search, stops, realtime)
├── flex_templates.py     # LINE Flex Message JSON builders (search results UI)
├── message_parser.py     # User input parsing (commands, search queries, favorites)
├── session.py            # In-memory session state (2-step search, timeouts)
├── storage.py            # JSON file persistence (search history, favorites)
├── data/                 # Runtime data directory (not committed to git)
│   └── search_history.json
├── docs/                 # Documentation
│   ├── deployment.md     # This file
│   └── images/           # README screenshot images
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variable template
└── .gitignore
```

## Troubleshooting

### Server won't start

- **"LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET must be set"** — Make sure your `.env` file exists and contains valid credentials. Run `cat .env` to verify.
- **Port already in use** — Another process is using the configured port. Check with `lsof -i :8083` and change `FLASK_PORT` if needed.

### LINE webhook verification fails

- Ensure the URL is accessible from the internet (not just localhost)
- The URL must use HTTPS with a valid SSL certificate
- The path must be exactly `/kcb_linebot/callback`

### Bot doesn't respond to messages

- Check the logs: `journalctl -u kcb_linebot.service -f`
- Verify the bus API is running: `curl http://localhost:8081/kcb_api/health`
- Make sure "Use webhook" is enabled in the LINE Developers Console
- Confirm auto-reply is disabled in the LINE console

### Search returns no results

- The bus API (kcb_api) may not be running or may not have data loaded
- Stop names must match exactly — check available stops in the kcb_api database
- After 21:00, the bot automatically searches next-day timetables
