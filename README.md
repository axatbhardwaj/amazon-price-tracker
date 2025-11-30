# Amazon Price Tracker

Track Amazon product prices and get notified when they drop below your target.

## Features

- 📊 Track multiple products from Amazon India
- 🔔 Desktop notifications when price hits target (Linux/macOS/Windows)
- 📉 Price drop alerts
- 📜 Price history saved to JSON
- 🔄 Exponential backoff on failures
- 🕵️ User-agent rotation to avoid blocking

## Setup

```bash
# Install dependencies
uv sync

# Run tracker
uv run tracker.py
```

## Configuration

Add products to `items.json`:

```json
[
  {
    "name": "Product Name",
    "url": "https://www.amazon.in/dp/PRODUCT_ID",
    "threshold": 5000
  }
]
```

| Field | Description |
|-------|-------------|
| `name` | Display name for the product |
| `url` | Amazon product URL |
| `threshold` | Target price for notification |

## Files

- `items.json` - Products to track
- `price_history.json` - Historical price data
- `tracker.log` - Log file

## How It Works

1. Checks prices every 60-120 minutes (randomized)
2. Saves price history with timestamps
3. Sends desktop notification when price ≤ threshold
4. Retries with exponential backoff on failures

## Requirements

- Python 3.9+
- `notify-send` (Linux) / built-in (macOS/Windows)

