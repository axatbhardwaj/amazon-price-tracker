import requests
from bs4 import BeautifulSoup
import json
import re

url = "https://www.flipkart.com/titan-np1825km01-karishma-blue-dial-silver-rose-gold-stainless-steel-strap-analog-watch-men/p/itm5d4774fc6dcdd?pid=WATFGH692F3YASTF"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

try:
    response = requests.get(url, headers=headers, timeout=10)
    print(f"Status Code: {response.status_code}")
    
    soup = BeautifulSoup(response.content, 'lxml')
    
    # Search for all divs and check their classes
    all_divs = soup.find_all('div')
    price_divs = []
    
    for div in all_divs:
        text = div.get_text().strip()
        if text.startswith('₹') and len(text) < 20:  # Likely a price
            price_divs.append((div.get('class'), text))
    
    print(f"Found {len(price_divs)} potential price divs:")
    for classes, text in price_divs[:10]:
        print(f"  Classes: {classes}, Text: {text}")
    
    # Also check for JSON data in scripts
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'price' in script.string.lower():
            # Try to extract JSON
            try:
                # Look for JSON objects
                json_match = re.search(r'\{[^{}]*"price"[^{}]*\}', script.string)
                if json_match:
                    print(f"\nFound price in script: {json_match.group(0)[:200]}")
            except:
                pass
                
except Exception as e:
    print(f"Error: {e}")
