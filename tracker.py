import json
import sys
import time
import random
import requests
import os
import logging
import tempfile
import shutil
import subprocess
import platform
from datetime import datetime
from scrapers import (
    fetch_amazon_price,
    fetch_flipkart_price,
    fetch_myntra_price,
)

# Configuration
ITEMS_FILE = "items.json"
HISTORY_FILE = "price_history.json"
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

# Setup logging
# Force UTF-8 for stdout/stderr to avoid UnicodeEncodeError on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

def setup_logging():
    # Create logs directory if it doesn't exist
    if not os.path.exists("logs"):
        os.makedirs("logs")
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join("logs", f"tracker_{timestamp}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ],
    )
    return log_file

logger = logging.getLogger(__name__)


def send_notification(title, message):
    """Send desktop notification (cross-platform)."""
    system = platform.system()
    try:
        if system == "Linux":
            subprocess.run(["notify-send", title, message], check=False)
        elif system == "Darwin":
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(["osascript", "-e", script], check=False)
        elif system == "Windows":
            # Use Popen for non-blocking execution and suppress output
            subprocess.Popen(
                [
                    "powershell",
                    "-Command",
                    f'[System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms"); [System.Windows.Forms.MessageBox]::Show("{message}", "{title}")',
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
    except FileNotFoundError:
        logger.warning(f"Notification command not found for {system}.")


def load_items():
    """Load items to track from JSON config."""
    try:
        with open(ITEMS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"{ITEMS_FILE} not found.")
        return []
    except json.JSONDecodeError:
        logger.error(f"Failed to decode {ITEMS_FILE}.")
        return []

def load_history():
    """Load price history from JSON file."""
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.warning(f"Corrupted history file {HISTORY_FILE}, starting fresh.")
        return {}

def save_history(history):
    """Save price history to JSON file atomically."""
    # Write to temp file first to avoid corruption on crash
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, dir=os.path.dirname(os.path.abspath(HISTORY_FILE))
        ) as tf:
            json.dump(history, tf, indent=2)
            temp_name = tf.name

        shutil.move(temp_name, HISTORY_FILE)
    except Exception as e:
        logger.error(f"Failed to save history: {e}")
        if os.path.exists(temp_name):
            os.remove(temp_name)


def check_price_drop(item_name, current_price, history, threshold, notification_callback=None, item_url=None):
    """Check if price dropped and notify if target reached."""
    last_price = None
    if item_name in history and history[item_name]:
        last_entry = history[item_name][-1]
        last_price = last_entry['price']

    if last_price and current_price < last_price:
        logger.info(f"📉 PRICE DROP: {item_name} | {last_price} -> {current_price}")

    if threshold > 0 and current_price <= threshold:
        logger.info(
            f"🔔 TARGET REACHED: {item_name} is {current_price} (Target: {threshold})"
        )
        if notification_callback:
            notification_callback(
                "🔔 Price Target Reached!",
                f"{item_name}\n₹{current_price} (Target: ₹{threshold})",
                item_url
            )
        else:
            send_notification(
                "🔔 Price Target Reached!",
                f"{item_name}\n₹{current_price} (Target: ₹{threshold})",
            )

def update_price_history(item_name, price, history):
    """Update the history dictionary with new price point."""
    if item_name not in history:
        history[item_name] = []

    timestamp = datetime.now().isoformat()
    history[item_name].append({
        "price": price,
        "timestamp": timestamp
    })


def process_item(item, history, notification_callback=None):
    """Process a single item."""
    name = item.get("name", "Unknown Item")
    url = item.get("url")
    threshold = item.get("threshold", 0.0)

    if not url:
        return

    logger.info(f"Checking: {name[:30]}...")
    
    source = item.get("Source", "amazon").lower()
    price = None
    
    if source == "myntra":
        price = fetch_myntra_price(url)
    elif source == "flipkart":
        price = fetch_flipkart_price(url)
    else:
        # Default to Amazon
        price = fetch_amazon_price(url)

    if price:
        logger.info(f"  Price: {price}")
        check_price_drop(name, price, history, threshold, notification_callback, url)
        update_price_history(name, price, history)
    else:
        logger.warning(f"  Could not find price for {name}")


def run_tracker():
    """Main loop to track prices."""
    setup_logging()
    logger.info("Starting Amazon Price Tracker (Ctrl+C to stop)...")

    try:
        while True:
            items = load_items()
            if not items:
                logger.error("No items found. Exiting.")
                break

            history = load_history()

            for item in items:
                process_item(item, history)
                # Small random delay between items to seem human
                time.sleep(random.uniform(2, 5))

            save_history(history)

            # Sleep cycle
            minutes = random.randint(60, 120)
            logger.info(f"Sleeping for {minutes} minutes...")
            time.sleep(minutes * 60)

    except KeyboardInterrupt:
        logger.info("Stopping tracker...")
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")


if __name__ == "__main__":
    run_tracker()
