import requests
import time
import json
import logging
from bs4 import BeautifulSoup
from .utils import get_headers, parse_price_text

logger = logging.getLogger(__name__)

def fetch_myntra_price(url, max_retries=5):
    """Fetch price from Myntra."""
    logger.info(f"Fetching Myntra URL: {url}")
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=get_headers(), timeout=30)
            logger.info(f"Response Status: {response.status_code}")
            if response.status_code == 200:
                logger.debug("Parsing HTML with BeautifulSoup...")
                soup = BeautifulSoup(response.content, "lxml")
                scripts = soup.find_all('script')
                logger.debug(f"Found {len(scripts)} scripts.")
                for script in scripts:
                    if script.string and 'window.__myx =' in script.string:
                        logger.debug("Found window.__myx script.")
                        content = script.string
                        start_marker = "window.__myx ="
                        start_index = content.find(start_marker) + len(start_marker)
                        json_str = content[start_index:].strip()
                        if json_str.endswith(";"):
                            json_str = json_str[:-1]
                        
                        try:
                            data = json.loads(json_str)
                            pdp_data = data.get('pdpData', {})
                            price = pdp_data.get('price', {}).get('discounted', 0) or pdp_data.get('price', {}).get('mrp', 0)
                            if price:
                                logger.info(f"Found price in JSON: {price}")
                                return float(price)
                        except (json.JSONDecodeError, ValueError):
                            logger.warning("Failed to parse Myntra JSON.")
                            continue
                
                # Fallback to selector if JSON fails (though JSON is more reliable)
                price_element = soup.select_one('.pdp-price')
                if price_element:
                    price_text = price_element.get_text()
                    logger.debug(f"Found price element: {price_text}")
                    price = parse_price_text(price_text)
                    if price:
                        logger.info(f"Successfully extracted price: {price}")
                        return price
                        
                logger.warning("  Price not found in Myntra page.")
                error_reason = "Price not found" # Set error reason
            else:
                logger.warning(f"  HTTP {response.status_code}")
                error_reason = f"HTTP {response.status_code}" # Set error reason
        except requests.RequestException as e:
            logger.warning(f"  Request error: {e}")
            error_reason = f"Request error: {e}" # Set error reason

        if attempt < max_retries - 1:
            # Exponential backoff with jitter: 2, 4, 8, 16, 32 seconds + random
            wait_time = (2 ** (attempt + 1)) + random.uniform(1, 3)
            logger.warning(f"  {error_reason}. Retry {attempt + 1}/{max_retries} in {wait_time:.1f}s...")
            time.sleep(wait_time)
            
    return None
