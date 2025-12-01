import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, CallbackQuery, Message, User, Chat
from telegram.ext import ContextTypes, ConversationHandler

from bot import (
    link,
    handle_notification_action,
    update_threshold_handler,
    THRESHOLD,
    NAME,
    LINK,
    NEW_THRESHOLD,
    ITEMS_FILE
)
import json
import os

@pytest.fixture
def mock_update_context():
    update = MagicMock(spec=Update)
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    
    # Mock message
    update.message = MagicMock(spec=Message)
    update.message.reply_text = AsyncMock()
    update.effective_chat.id = 123456789
    
    # Mock callback query
    update.callback_query = MagicMock(spec=CallbackQuery)
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    
    return update, context

@pytest.mark.asyncio
async def test_link_handler_amazon(mock_update_context):
    update, context = mock_update_context
    update.message.text = "https://www.amazon.in/dp/B09V2Q2331"
    
    with patch('bot.fetch_amazon_price') as mock_fetch:
        mock_fetch.return_value = {"title": "Test Product", "price": 999.0}
        
        state = await link(update, context)
        
        assert context.user_data.get("source") == "amazon"
        assert context.user_data.get("name") == "Test Product"
        assert state == THRESHOLD
        update.message.reply_text.assert_called()

@pytest.mark.asyncio
async def test_link_handler_invalid_url(mock_update_context):
    update, context = mock_update_context
    update.message.text = "https://google.com"
    
    state = await link(update, context)
    
    assert state == LINK
    assert "couldn't detect" in update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_handle_notification_action_delete(mock_update_context, tmp_path):
    update, context = mock_update_context
    
    # Setup items file
    items_file = tmp_path / "items.json"
    items = [
        {"name": "Item 1", "url": "http://item1", "threshold": 100, "user_id": 123},
        {"name": "Item 2", "url": "http://item2", "threshold": 200, "user_id": 123}
    ]
    items_file.write_text(json.dumps(items))
    
    with patch('bot.ITEMS_FILE', str(items_file)), patch('tracker.ITEMS_FILE', str(items_file)):
        # Delete Item 1 (index 0)
        update.callback_query.data = "delete_0"
        
        await handle_notification_action(update, context)
        
        # Verify
        new_items = json.loads(items_file.read_text())
        assert len(new_items) == 1
        assert new_items[0]["name"] == "Item 2"
        update.callback_query.edit_message_text.assert_called_with(text="Stopped tracking 'Item 1'.")

@pytest.mark.asyncio
async def test_handle_notification_action_update(mock_update_context, tmp_path):
    update, context = mock_update_context
    
    # Setup items file
    items_file = tmp_path / "items.json"
    items = [{"name": "Item 1", "url": "http://item1", "threshold": 100, "user_id": 123}]
    items_file.write_text(json.dumps(items))
    
    with patch('bot.ITEMS_FILE', str(items_file)), patch('tracker.ITEMS_FILE', str(items_file)):
        update.callback_query.data = "update_0"
        
        state = await handle_notification_action(update, context)
        
        assert state == NEW_THRESHOLD
        assert context.user_data["update_item_index"] == 0
        assert context.user_data["update_item_name"] == "Item 1"
        update.callback_query.edit_message_text.assert_called()

@pytest.mark.asyncio
async def test_update_threshold_handler(mock_update_context, tmp_path):
    update, context = mock_update_context
    
    # Setup items file
    items_file = tmp_path / "items.json"
    items = [{"name": "Item 1", "url": "http://item1", "threshold": 100, "user_id": 123}]
    items_file.write_text(json.dumps(items))
    
    # Setup context
    context.user_data["update_item_index"] = 0
    context.user_data["update_item_name"] = "Item 1"
    
    # User sends new threshold
    update.message.text = "150"
    
    with patch('bot.ITEMS_FILE', str(items_file)), patch('tracker.ITEMS_FILE', str(items_file)):
        state = await update_threshold_handler(update, context)
        
        assert state == ConversationHandler.END
        
        # Verify file update
        new_items = json.loads(items_file.read_text())
        assert new_items[0]["threshold"] == 150.0
        
        # Verify context cleared
        assert "update_item_index" not in context.user_data
