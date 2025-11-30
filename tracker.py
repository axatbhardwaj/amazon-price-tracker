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
from bs4 import BeautifulSoup

# Configuration
ITEMS_FILE = "items.json"
HISTORY_FILE = "price_history.json"
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

# Setup logging
# Force UTF-8 for stdout/stderr to avoid UnicodeEncodeError on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler("tracker.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ],
)
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


# List of User-Agents to rotate
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
]

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

def parse_price_text(price_text):
    """Parse price text and return float value."""
    # Remove currency symbols, commas, spaces
    # Handle case with multiple dots (keep only the last one if looks like decimal)
    clean_price = ''.join(c for c in price_text if c.isdigit() or c == '.')

    if not clean_price:
        return None

    # If multiple dots, assumption: last one is decimal, others are separators (rare in scraping clean output but possible)
    if clean_price.count(".") > 1:
        clean_price = clean_price.replace(".", "", clean_price.count(".") - 1)

    try:
        return float(clean_price)
    except ValueError:
        return None

def get_price(soup):
    """Extract price from BeautifulSoup object using common Amazon selectors."""
    selectors = [
        # Amazon India specific
        '.a-price-whole',
        '#corePriceDisplay_desktop_feature_div .a-price-whole',
        '#corePrice_desktop .a-price-whole',
        # General Amazon selectors
        '.a-price .a-offscreen',
        '#priceblock_ourprice',
        '#priceblock_dealprice',
        '#corePriceDisplay_desktop_feature_div .a-offscreen',
        '#apex_desktop .a-offscreen',
        '.a-price span[aria-hidden="true"]',
        '#tp_price_block_total_price_ww .a-offscreen',
        '.reinventPricePriceToPayMargin .a-offscreen',
    ]

    for selector in selectors:
        element = soup.select_one(selector)
        if not element:
            continue
        price = parse_price_text(element.get_text())
        if price:
            return price
    return None


def get_headers():
    """Generate random headers for requests."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8,hi;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Upgrade-Insecure-Requests": "1",
    }


def fetch_price(url, max_retries=5):
    """Fetch page content and extract price with exponential backoff."""
    for attempt in range(max_retries):
        error_reason = None
        try:
            response = requests.get(url, headers=get_headers(), timeout=30)

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "lxml")
                price = get_price(soup)
                if price:
                    return price
                error_reason = "Price element not found in HTML (selectors didn't match)"
            elif response.status_code == 503:
                error_reason = "503 Service Unavailable (Amazon blocking)"
            elif response.status_code == 429:
                error_reason = "429 Too Many Requests (rate limited)"
            elif response.status_code == 403:
                error_reason = "403 Forbidden (blocked/bot detected)"
            elif response.status_code == 404:
                error_reason = "404 Not Found (invalid URL or product removed)"
            else:
                error_reason = f"HTTP {response.status_code}"

        except requests.Timeout:
            error_reason = "Request timed out"
        except requests.ConnectionError:
            error_reason = "Connection failed"
        except requests.RequestException as e:
            error_reason = f"Request error: {e}"

        if attempt < max_retries - 1:
            wait_time = (2**attempt) + random.random()
            logger.warning(f"  {error_reason}. Retry {attempt + 1}/{max_retries} in {wait_time:.1f}s...")
            time.sleep(wait_time)
        else:
            logger.error(f"  Failed after {max_retries} attempts: {error_reason}")

    return None


def check_price_drop(item_name, current_price, history, threshold):
    """Check if price dropped and notify if target reached."""
    if item_name not in history or not history[item_name]:
        return

    last_entry = history[item_name][-1]
    last_price = last_entry['price']

    if current_price < last_price:
        logger.info(f"📉 PRICE DROP: {item_name} | {last_price} -> {current_price}")

    if threshold > 0 and current_price <= threshold:
        logger.info(
            f"🔔 TARGET REACHED: {item_name} is {current_price} (Target: {threshold})"
        )
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


def process_item(item, history):
    """Process a single item."""
    name = item.get("name", "Unknown Item")
    url = item.get("url")
    threshold = item.get("threshold", 0.0)

    if not url:
        return

    logger.info(f"Checking: {name[:30]}...")
    price = fetch_price(url)

    if price:
        logger.info(f"  Price: {price}")
        check_price_drop(name, price, history, threshold)
        update_price_history(name, price, history)
    else:
        logger.warning(f"  Could not find price for {name}")


def run_tracker():
    """Main loop to track prices."""
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
