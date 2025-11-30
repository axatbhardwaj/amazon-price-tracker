import json
import time
import random
import requests
import os
from datetime import datetime
from bs4 import BeautifulSoup

# Configuration
ITEMS_FILE = "items.json"
HISTORY_FILE = "price_history.json"

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
        print(f"Error: {ITEMS_FILE} not found.")
        return []
    except json.JSONDecodeError:
        print(f"Error: Failed to decode {ITEMS_FILE}.")
        return []

def load_history():
    """Load price history from JSON file."""
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_history(history):
    """Save price history to JSON file."""
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

def parse_price_text(price_text):
    """Parse price text and return float value."""
    # Remove currency symbols, commas, spaces
    clean_price = ''.join(c for c in price_text if c.isdigit() or c == '.')
    if not clean_price:
        return None
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

def fetch_price(url):
    """Fetch page content and extract price."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8,hi;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            print(f"Failed to fetch {url}: Status {response.status_code}")
            return None
        
        soup = BeautifulSoup(response.content, 'lxml')
        return get_price(soup)
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

def check_price_drop(item_name, current_price, history, threshold):
    """Check if price dropped and log it."""
    if item_name not in history or not history[item_name]:
        return
        
    last_entry = history[item_name][-1]
    last_price = last_entry['price']
    
    if current_price < last_price:
        print(f"📉 PRICE DROP ALERT: {item_name} dropped from {last_price} to {current_price}!")
    
    if current_price <= threshold:
        print(f"🔔 TARGET REACHED: {item_name} is {current_price} (Threshold: {threshold})")

def update_price_history(item_name, price, history):
    """Update the history dictionary with new price point."""
    if item_name not in history:
        history[item_name] = []
        
    timestamp = datetime.now().isoformat()
    history[item_name].append({
        "price": price,
        "timestamp": timestamp
    })

def run_tracker():
    """Main loop to track prices."""
    print("Starting Amazon Price Tracker...")
    print("Press Ctrl+C to stop.")
    
    while True:
        items = load_items()
        if not items:
            print("No items to track. Exiting.")
            break
            
        history = load_history()
        
        for item in items:
            name = item.get('name', 'Unknown Item')
            url = item.get('url')
            threshold = item.get('threshold', 0.0)
            
            if not url:
                continue
                
            print(f"Checking price for: {name}")
            price = fetch_price(url)
            
            if price:
                print(f"  Current Price: {price}")
                check_price_drop(name, price, history, threshold)
                update_price_history(name, price, history)
            else:
                print(f"  Could not find price for {name}")
                
        save_history(history)
        
        # Random sleep between 60 and 120 minutes
        minutes = random.randint(60, 120)
        print(f"\nSleeping for {minutes} minutes...")
        time.sleep(minutes * 60)

if __name__ == "__main__":
    run_tracker()

