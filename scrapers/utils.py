import random

# List of User-Agents to rotate
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
]

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
