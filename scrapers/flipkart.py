import requests
import time
import random
import json
import logging
from bs4 import BeautifulSoup
from .utils import get_headers, parse_price_text

logger = logging.getLogger(__name__)

def get_title(soup):
    """Extract product title from Flipkart."""
    selectors = [
        'span.VU-ZEz',
        'h1._6EBuvT',
        'h1',
    ]
    for selector in selectors:
        element = soup.select_one(selector)
        if element:
            return element.get_text().strip()
    return "Unknown Product"

def fetch_flipkart_price(url, max_retries=5):
    """Fetch price and title from Flipkart."""
    logger.info(f"Fetching Flipkart URL: {url}")
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=get_headers(), timeout=30)
            logger.info(f"Response Status: {response.status_code}")
            if response.status_code == 200:
                logger.debug("Parsing HTML with BeautifulSoup...")
                soup = BeautifulSoup(response.content, "lxml")
                
                title = get_title(soup)

                # Try JSON-LD structured data first (most reliable)
                scripts = soup.find_all('script', type='application/ld+json')
                logger.debug(f"Found {len(scripts)} JSON-LD scripts.")
                for script in scripts:
                    if script.string:
                        try:
                            data = json.loads(script.string)
                            # Handle both single object and array of objects
                            if isinstance(data, list):
                                for item in data:
                                    if item.get('@type') == 'Product' and 'offers' in item:
                                        price = item['offers'].get('price')
                                        if price:
                                            logger.info(f"Found price in JSON-LD (list): {price}")
                                            return {"price": float(price), "title": title}
                            elif isinstance(data, dict):
                                if data.get('@type') == 'Product' and 'offers' in data:
                                    price = data['offers'].get('price')
                                    if price:
                                        logger.info(f"Found price in JSON-LD (dict): {price}")
                                        return {"price": float(price), "title": title}
                                # Direct Offer type
                                if data.get('@type') == 'Offer' and 'price' in data:
                                    logger.info(f"Found price in JSON-LD (Offer): {data['price']}")
                                    return {"price": float(data['price']), "title": title}
                        except (json.JSONDecodeError, ValueError, KeyError):
                            continue
                
                # Fallback to CSS selectors
                price_selectors = [
                    'div.Nx9bqj.CxhGGd',  # Current common selector
                    'div.hZ3P6w.bnqy13',  # Alternative
                    'div._30jeq3._16Jk6d',
                    'div.hl05eU',
                ]
                
                for selector in price_selectors:
                    element = soup.select_one(selector)
                    if element:
                        price_text = element.get_text()
                        logger.debug(f"Found price element with selector '{selector}': {price_text}")
                        price = parse_price_text(price_text)
                        if price:
                            logger.info(f"Successfully extracted price: {price}")
                            return {"price": price, "title": title}
                
                logger.warning("  Price not found in Flipkart page.")
                error_reason = "Price not found"
            else:
                logger.warning(f"  HTTP {response.status_code}")
                error_reason = f"HTTP {response.status_code}"
        except requests.RequestException as e:
            logger.warning(f"  Request error: {e}")
            error_reason = f"Request error: {e}"

        if attempt < max_retries - 1:
            # Exponential backoff with jitter: 2, 4, 8, 16, 32 seconds + random
            wait_time = (2 ** (attempt + 1)) + random.uniform(1, 3)
            logger.warning(f"  {error_reason}. Retry {attempt + 1}/{max_retries} in {wait_time:.1f}s...")
            time.sleep(wait_time)
        else:
            logger.warning(f"  Max retries ({max_retries}) reached for {url}.")
            
    return None
