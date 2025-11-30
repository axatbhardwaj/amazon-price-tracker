import requests
import time
import json
import logging
from bs4 import BeautifulSoup
from .utils import get_headers, parse_price_text

logger = logging.getLogger(__name__)

def fetch_myntra_price(url, max_retries=5):
    """Fetch price from Myntra."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=get_headers(), timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "lxml")
                scripts = soup.find_all('script')
                for script in scripts:
                    if script.string and 'window.__myx =' in script.string:
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
                                return float(price)
                        except (json.JSONDecodeError, ValueError):
                            continue
                
                # Fallback to selector if JSON fails (though JSON is more reliable)
                price_element = soup.select_one('.pdp-price')
                if price_element:
                    price = parse_price_text(price_element.get_text())
                    if price:
                        return price
                        
                logger.warning("  Price not found in Myntra page.")
            else:
                logger.warning(f"  HTTP {response.status_code}")
        except requests.RequestException as e:
            logger.warning(f"  Request error: {e}")

        if attempt < max_retries - 1:
            time.sleep(2)
            
    return None
