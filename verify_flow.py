import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from bot import link, THRESHOLD, NAME, LINK

async def test_link_handler():
    print("Testing link handler...")
    
    # Mock Update and Context
    update = MagicMock()
    context = MagicMock()
    context.user_data = {}
    
    # Test Case 1: Valid Amazon URL
    print("\nTest Case 1: Valid Amazon URL")
    update.message.text = "https://www.amazon.in/dp/B09V2Q2331"
    update.message.reply_text = AsyncMock()
    
    # Mock scraper
    with patch('bot.fetch_amazon_price') as mock_fetch:
        mock_fetch.return_value = {"title": "Test Product", "price": 999.0}
        
        state = await link(update, context)
        
        if context.user_data.get("source") == "amazon":
            print("✅ Platform detected: Amazon")
        else:
            print(f"❌ Platform detection failed: {context.user_data.get('source')}")
            
        if context.user_data.get("name") == "Test Product":
            print("✅ Product title fetched: Test Product")
        else:
            print(f"❌ Product title fetch failed: {context.user_data.get('name')}")
            
        if state == THRESHOLD:
            print("✅ State transition to THRESHOLD")
        else:
            print(f"❌ State transition failed: {state}")

    # Test Case 2: Invalid URL
    print("\nTest Case 2: Invalid URL")
    update.message.text = "https://google.com"
    context.user_data = {}
    
    state = await link(update, context)
    
    if state == LINK:
        print("✅ Invalid URL rejected")
    else:
        print(f"❌ Invalid URL accepted (State: {state})")

if __name__ == "__main__":
    asyncio.run(test_link_handler())
