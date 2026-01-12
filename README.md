# Kyoto City Bus LINE Bot

A LINE bot that provides real-time Kyoto City Bus route information. Search for bus routes by entering departure and destination stops and view results in a beautiful Flex Message format.

![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![Flask](https://img.shields.io/badge/flask-3.0.0-green.svg)
![LINE Bot SDK](https://img.shields.io/badge/line--bot--sdk-3.21.0-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

> **⚠️ Important**: This bot requires a self-hosted Kyoto City Bus API. Please set up [kcb_api](https://github.com/kmch4n/kcb_api) first before using this bot.

## Features

- 🚌 **Bus Route Search** - Search by departure and destination stops
- 📍 **Location-based Search** - Find nearby bus stops using your location
- ⏱️ **Real-time Information** - Display bus arrival time and current position
- 🎨 **Rich UI** - Beautiful Flex Message format with color-coded routes
- 📅 **Auto Schedule Detection** - Automatically detects weekday/Saturday/Sunday schedules

## Prerequisites

Before installing this bot, you need to set up the Kyoto City Bus API:

1. **Set up kcb_api** - Follow the instructions at [github.com/kmch4n/kcb_api](https://github.com/kmch4n/kcb_api)
2. **Get LINE credentials** - Create a LINE Bot account at [LINE Developers Console](https://developers.line.biz/console/)

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd kcb_linebot
   ```

2. **Install dependencies**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

## Configuration

Edit `.env` file:

```bash
# LINE Messaging API (Required)
LINE_CHANNEL_ACCESS_TOKEN=your_token_here
LINE_CHANNEL_SECRET=your_secret_here

# Kyoto City Bus API (Required)
API_KEY=your_api_key_here
API_BASE_URL=http://localhost:8081/kcb_api

# Server (Optional)
FLASK_PORT=8083
FLASK_DEBUG=False
```

## Usage

```bash
source .venv/bin/activate
python3 main.py
```

Server starts on `http://localhost:8083`

### LINE Webhook Setup

1. Go to [LINE Developers Console](https://developers.line.biz/console/)
2. Set Webhook URL: `https://your-domain.com/kcb_linebot/callback`
3. Enable "Use webhook"

## How to Use the Bot

### Basic Search

Send bus stop names (in Japanese):
```
四条河原町 京都駅前
```

Or with direction indicator:
```
四条河原町から京都駅前
四条河原町→京都駅前
```

### Two-step Search

1. Send departure stop only:
   ```
   四条河原町
   ```

2. Bot asks for destination, reply with:
   ```
   京都駅前
   ```

### Location-based Search

1. Share your location in LINE
2. Select nearby stop from Quick Reply
3. Enter destination stop

### Real-time Information

- **🔴 Bus Approaching** - 0-3 minutes until departure
- **✅ On Time** - 4-10 minutes until departure
- Buses departing in >10 minutes: no real-time info shown

## Project Structure

```
kcb_linebot/
├── main.py               # Flask webhook server
├── config.py             # Configuration management
├── handlers.py           # LINE message handlers
├── bus_api.py            # Bus API client
├── flex_templates.py     # Flex Message templates
├── message_parser.py     # Message parsing
├── session.py            # Session management
└── requirements.txt      # Dependencies
```

## Tech Stack

- Python 3.12+
- Flask 3.0.0
- LINE Bot SDK 3.21.0

## License

MIT License

---

**Last Updated**: 2026-01-12
**Version**: 1.0.0
