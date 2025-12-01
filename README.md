# Multi-Site Price Tracker & Telegram Bot

Track product prices from Amazon, Flipkart, and Myntra and get notified via **Telegram** or desktop notifications when they drop below your target.

## Features

- 📊 **Multi-Platform**: Track products from Amazon, Flipkart, and Myntra.
- 🤖 **Telegram Bot**: 
    - Add items via chat with a guided conversation.
    - **Auto-start**: Tracking starts automatically on bot startup.
    - **Smart Notifications**: Alerts include product links and are sent to the specific user.
    - **Platform UI**: Easy-to-use buttons for selecting platforms.
    - **Immediate Check**: Use `/check` to verify prices instantly.
- 🖥️ **CLI Mode**: Run as a background script with system notifications (Linux/macOS/Windows).
- 📉 **Price Drop Alerts**: Get notified when price hits your target or drops.
- 📜 **History**: Price history saved to JSON.
- 🛡️ **Robust**: Exponential backoff and user-agent rotation to avoid blocking.
- 📝 **Logging**: Detailed timestamped logs in `logs/` directory.

## Setup

1.  **Run Setup Command**:
    This will install dependencies and create a `.env` file for you.
    ```bash
    make setup
    ```

2.  **Configure Token**:
    Open the newly created `.env` file and paste your Telegram Bot Token:
    ```env
    TELEGRAM_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
    ```

## Usage

### 🤖 Run Telegram Bot

```bash
make run-bot
```

**Bot Commands**:
- `/start`: Welcome message.
- `/help`: Show usage instructions.
- `/add`: Add a new item (guided flow: Link -> Name -> Platform -> Price).
- `/delete`: Remove an item from your tracking list.
- `/check`: Trigger an immediate price check.
- `/cancel`: Cancel current operation.

### 🖥️ Run CLI Tracker

```bash
make run-cli
```
*Note: CLI mode uses `items.json` but sends desktop notifications instead of Telegram messages.*

## Configuration

### `items.json`
Stores the list of tracked items. The bot manages this automatically, but you can edit it manually:

```json
[
  {
    "name": "Headphones",
    "url": "https://www.amazon.in/dp/PRODUCT_ID",
    "threshold": 5000,
    "Source": "amazon",
    "user_id": 123456789
  }
]
```

| Field | Description |
|-------|-------------|
| `name` | Display name |
| `url` | Product URL |
| `threshold` | Target price |
| `Source` | "amazon", "flipkart", or "myntra" |
| `user_id` | (Optional) Telegram Chat ID for notifications |

## Development

- **`bot.py`**: Telegram bot logic (handlers, job queue).
- **`tracker.py`**: Core tracking logic and CLI entry point.
- **`scrapers/`**: Site-specific scrapers (Amazon, Flipkart, Myntra).
- **`logs/`**: Timestamped log files (e.g., `tracker_20231027_103000.log`).

### Commands

- `make setup`: Install dependencies and create .env file.
- `make install`: Install dependencies only.
- `make run-bot`: Run the Telegram bot.
- `make run-cli`: Run the CLI tracker.
- `make test`: Run tests.
- `make clean`: Clean up cache files.

## Requirements

- Python 3.9+
- `uv` (for dependency management)
- Telegram Bot Token (from @BotFather)

