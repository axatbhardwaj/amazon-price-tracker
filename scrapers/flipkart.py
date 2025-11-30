import requests
import time
import json
import logging
from bs4 import BeautifulSoup
from .utils import get_headers, parse_price_text

logger = logging.getLogger(__name__)

def fetch_flipkart_price(url, max_retries=5):
    """Fetch price from Flipkart."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=get_headers(), timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "lxml")
                
                # Try JSON-LD structured data first (most reliable)
                scripts = soup.find_all('script', type='application/ld+json')
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
                                            return float(price)
                            elif isinstance(data, dict):
                                if data.get('@type') == 'Product' and 'offers' in data:
                                    price = data['offers'].get('price')
                                    if price:
                                        return float(price)
                                # Direct Offer type
                                if data.get('@type') == 'Offer' and 'price' in data:
                                    return float(data['price'])
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
                        price = parse_price_text(element.get_text())
                        if price:
                            return price
                
                logger.warning("  Price not found in Flipkart page.")
            else:
                logger.warning(f"  HTTP {response.status_code}")
        except requests.RequestException as e:
            logger.warning(f"  Request error: {e}")

        if attempt < max_retries - 1:
            time.sleep(2)
            
    return None
