import requests
import time
import random
import logging
from bs4 import BeautifulSoup
from .utils import get_headers, parse_price_text

logger = logging.getLogger(__name__)

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

def fetch_amazon_price(url, max_retries=5):
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
