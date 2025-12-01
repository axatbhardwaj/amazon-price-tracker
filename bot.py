import logging
import os
import asyncio
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
from tracker import load_items, save_history, load_history, process_item, ITEMS_FILE, setup_logging
from scrapers import fetch_amazon_price, fetch_flipkart_price, fetch_myntra_price
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Enable logging
setup_logging()
logger = logging.getLogger(__name__)

# States for ConversationHandler
LINK, NAME, PLATFORM, THRESHOLD = range(4)
DELETE_SELECT = 0
NEW_THRESHOLD = 0

async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the delete item conversation."""
    user_id = update.effective_chat.id
    items = load_items()
    
    # Filter items for this user
    user_items = []
    for i, item in enumerate(items):
        if item.get("user_id") == user_id:
            user_items.append((i, item))
            
    if not user_items:
        await update.message.reply_text("You are not tracking any items.")
        return ConversationHandler.END
        
    context.user_data["user_items"] = user_items
    
    # Create buttons for each item
    keyboard = [[f"{item['name']}"] for _, item in user_items]
    keyboard.append(["Cancel"])
    
    await update.message.reply_text(
        "Select an item to stop tracking:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    )
    return DELETE_SELECT

async def delete_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the item deletion."""
    text = update.message.text
    if text == "Cancel":
        await update.message.reply_text("Operation cancelled.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
        
    user_items = context.user_data.get("user_items", [])
    
    # Find the selected item
    selected_index = -1
    for index, item in user_items:
        if item["name"] == text:
            selected_index = index
            break
            
    if selected_index != -1:
        # We need to be careful about indices shifting if multiple users delete at once, 
        # but for this simple file-based approach, we'll reload and check.
        # Actually, let's use the delete_item function we added to tracker.py
        # But wait, delete_item takes an index. If the file changed, the index might be wrong.
        # A safer way is to load, find by matching all fields, and delete.
        
        # Let's do it safely here
        items = load_items()
        # Find the item that matches exactly
        found = False
        for i, item in enumerate(items):
            # Check if it matches the one we selected (using name and user_id should be enough for now)
            if item.get("name") == text and item.get("user_id") == update.effective_chat.id:
                items.pop(i)
                found = True
                break
        
        if found:
            with open(ITEMS_FILE, 'w') as f:
                json.dump(items, f, indent=2)
            await update.message.reply_text(f"Stopped tracking '{text}'.", reply_markup=ReplyKeyboardRemove())
        else:
            await update.message.reply_text("Could not find that item. Maybe it was already deleted?", reply_markup=ReplyKeyboardRemove())
            
    else:
        await update.message.reply_text("Invalid selection. Please try /delete again.", reply_markup=ReplyKeyboardRemove())

    return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks for the link."""
    await update.message.reply_text(
        "Hi! I'm your Amazon Price Tracker Bot.\n"
        "Send /add to start tracking a new item.\n"
        "Send /check to check prices immediately.\n"
        "Send /help to see how to use me.\n"
        "Send /cancel to stop the current operation."
    )
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays info on how to use the bot."""
    help_text = (
        "🤖 *Price Tracker Bot Help*\n\n"
        "Here are the commands you can use:\n\n"
        "1. */add* - Start tracking a new product.\n"
        "   - You'll be asked for the product link.\n"
        "   - Then give it a name.\n"
        "   - Select the platform (Amazon, Flipkart, Myntra).\n"
        "   - Set your target price.\n\n"
        "2. */check* - Check prices for all your items right now.\n\n"
        "3. */delete* - Stop tracking an item.\n\n"
        "4. */cancel* - Stop whatever you're doing.\n\n"
        "5. */start* - Show the welcome message.\n\n"
        "🔔 *Notifications*:\n"
        "I'll automatically check prices every 30 minutes. If a price drops below your target, I'll send you a message with the link!"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the add item conversation."""
    await update.message.reply_text(
        "Let's track a new item! First, please send me the product link."
    )
    return LINK

async def link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the link, validates it, and tries to fetch details."""
    url = update.message.text
    context.user_data["url"] = url
    
    # Detect platform
    source = None
    if "amazon" in url or "amzn" in url:
        source = "amazon"
    elif "flipkart" in url:
        source = "flipkart"
    elif "myntra" in url:
        source = "myntra"
        
    if not source:
        await update.message.reply_text(
            "I couldn't detect the platform from that link. Please make sure it's a valid Amazon, Flipkart, or Myntra URL.\n"
            "Please send the link again."
        )
        return LINK
        
    context.user_data["source"] = source
    await update.message.reply_text(f"Detected platform: {source.capitalize()}. Fetching details...")
    
    # Fetch details
    result = None
    try:
        if source == "amazon":
            result = fetch_amazon_price(url)
        elif source == "flipkart":
            result = fetch_flipkart_price(url)
        elif source == "myntra":
            result = fetch_myntra_price(url)
    except Exception as e:
        logger.error(f"Error fetching details: {e}")
        
    if result:
        title = result.get('title', 'Unknown Item')
        price = result.get('price', 0.0)
        
        context.user_data["name"] = title
        
        await update.message.reply_text(
            f"Found: *{title}*\n"
            f"Current Price: ₹{price}\n\n"
            "What is your target price threshold? (e.g., 1000)",
            parse_mode="Markdown"
        )
        return THRESHOLD
    else:
        await update.message.reply_text(
            "Could not automatically fetch details. Let's do it manually.\n"
            "What should I call this item?"
        )
        return NAME

async def name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the name and asks for the platform."""
    context.user_data["name"] = update.message.text
    
    # If we already detected the source in the link step (but failed to fetch), we can skip asking
    if context.user_data.get("source"):
         await update.message.reply_text(
            "What is your target price threshold? (e.g., 1000)",
            reply_markup=ReplyKeyboardRemove(),
        )
         return THRESHOLD

    reply_keyboard = [["Amazon", "Flipkart", "Myntra"]]
    await update.message.reply_text(
        "Nice name! Now, select the platform:",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder="Select platform"
        ),
    )
    return PLATFORM

async def platform_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the platform and asks for the threshold."""
    context.user_data["source"] = update.message.text.lower()
    await update.message.reply_text(
        "Great! Finally, what is your target price threshold? (e.g., 1000)",
        reply_markup=ReplyKeyboardRemove(),
    )
    return THRESHOLD

async def threshold(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the threshold and adds the item."""
    try:
        threshold_value = float(update.message.text)
        context.user_data["threshold"] = threshold_value
        
        # Add item to list
        new_item = {
            "name": context.user_data["name"],
            "url": context.user_data["url"],
            "Source": context.user_data["source"],
            "threshold": context.user_data["threshold"],
            "user_id": update.effective_chat.id 
        }
        
        items = load_items()
        # Basic check to avoid duplicates could be added here
        items.append(new_item)
        
        with open(ITEMS_FILE, 'w') as f:
            json.dump(items, f, indent=2)
            
        await update.message.reply_text(f"Item '{new_item['name']}' added successfully! Tracking started.")
        
    except ValueError:
        await update.message.reply_text("Invalid price format. Please try adding the item again.")
        return ConversationHandler.END

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text("Operation cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def run_tracking_cycle(app):
    """Core logic to check prices and notify."""
    items = load_items()
    history = load_history()
    
    loop = asyncio.get_running_loop()
    
    for item in items:
        user_id = item.get("user_id")
        if not user_id:
            logger.warning(f"Item {item.get('name', 'Unknown')} has no user_id. Skipping notification.")
            continue
            
        async def item_notification_callback(title, message, item=None):
            text = f"{title}\n{message}"
            reply_markup = None
            
            if item:
                item_url = item.get("url")
                if item_url:
                    text += f"\n\nLink: {item_url}"
                
                # Add inline buttons
                # We need a way to identify the item. Using URL hash or just index if we reload.
                # Let's find the index of this item in the current list
                try:
                    # Reload items to get fresh index
                    current_items = load_items()
                    # Find index by matching URL and Name
                    item_index = -1
                    for idx, curr_item in enumerate(current_items):
                        if curr_item.get("url") == item.get("url") and curr_item.get("name") == item.get("name"):
                            item_index = idx
                            break
                    
                    if item_index != -1:
                        keyboard = [
                            [
                                InlineKeyboardButton("Update Threshold", callback_data=f"update_{item_index}"),
                                InlineKeyboardButton("Stop Tracking", callback_data=f"delete_{item_index}"),
                            ]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                except Exception as e:
                    logger.error(f"Error creating inline buttons: {e}")

            try:
                await app.bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup)
            except Exception as e:
                logger.error(f"Failed to send message to {user_id}: {e}")

        # Using run_in_executor to avoid blocking the bot
        await loop.run_in_executor(
            None, 
            lambda i=item: process_item(i, history, lambda t, m, it: asyncio.run_coroutine_threadsafe(item_notification_callback(t, m, it), loop))
        )
        
    save_history(history)

async def check_prices(context: ContextTypes.DEFAULT_TYPE):
    """Periodic job to check prices."""
    await run_tracking_cycle(context.application)

async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually trigger a price check."""
    await update.message.reply_text("Checking prices now...")
    try:
        await run_tracking_cycle(context.application)
        await update.message.reply_text("Price check complete.")
    except Exception as e:
        logger.error(f"Error during manual check: {e}")
        await update.message.reply_text("An error occurred during the price check.")


async def send_heartbeat(context: ContextTypes.DEFAULT_TYPE):
    """Sends a heartbeat to Uptime Kuma."""
    push_url = os.getenv("UPTIME_KUMA_PUSH_URL")
    if not push_url:
        logger.warning("UPTIME_KUMA_PUSH_URL not set. Skipping heartbeat.")
        return

    try:
        response = requests.get(push_url)
        if response.status_code == 200:
            logger.info("Heartbeat sent successfully.")
        else:
            logger.error(f"Failed to send heartbeat: {response.status_code}")
    except Exception as e:
        logger.error(f"Error sending heartbeat: {e}")

async def handle_notification_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query
    await query.answer()

    data = query.data
    action, index_str = data.split("_")
    index = int(index_str)
    
    items = load_items()
    
    if index < 0 or index >= len(items):
        await query.edit_message_text(text=f"Item not found or already deleted.")
        return

    item = items[index]

    if action == "delete":
        # Remove item
        items.pop(index)
        with open(ITEMS_FILE, 'w') as f:
            json.dump(items, f, indent=2)
        await query.edit_message_text(text=f"Stopped tracking '{item['name']}'.")
        
    elif action == "update":
        context.user_data["update_item_index"] = index
        context.user_data["update_item_name"] = item["name"]
        
        await query.edit_message_text(text=f"Please enter the new target price for '{item['name']}':")
        return NEW_THRESHOLD

async def update_threshold_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Updates the threshold for the selected item."""
    index = context.user_data.get("update_item_index")
    if index is None:
        await update.message.reply_text("Something went wrong. Please try again.")
        return ConversationHandler.END
        
    try:
        new_threshold = float(update.message.text)
        
        items = load_items()
        # Verify index is still valid and item matches (basic check)
        if index < len(items) and items[index]["name"] == context.user_data.get("update_item_name"):
            items[index]["threshold"] = new_threshold
            with open(ITEMS_FILE, 'w') as f:
                json.dump(items, f, indent=2)
            await update.message.reply_text(f"Threshold for '{items[index]['name']}' updated to ₹{new_threshold}.")
        else:
            await update.message.reply_text("Item not found or list changed. Please try again.")
            
    except ValueError:
        await update.message.reply_text("Invalid price format.")
        
    # Clear state
    context.user_data.pop("update_item_index", None)
    context.user_data.pop("update_item_name", None)
    
    return ConversationHandler.END

def main() -> None:
    """Run the bot."""
    # Ensure items.json exists
    if not os.path.exists(ITEMS_FILE):
        with open(ITEMS_FILE, 'w') as f:
            json.dump([], f)
        logger.info(f"Created empty {ITEMS_FILE}")

    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN environment variable not set.")
        return

    application = Application.builder().token(token).build()

    # Add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, link)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_handler)],
            PLATFORM: [MessageHandler(filters.TEXT & ~filters.COMMAND, platform_handler)],
            THRESHOLD: [MessageHandler(filters.TEXT & ~filters.COMMAND, threshold)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Delete conversation handler
    delete_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("delete", delete_start)],
        states={
            DELETE_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Update threshold conversation
    update_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_notification_action, pattern="^update_")],
        states={
            NEW_THRESHOLD: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_threshold_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False # Important for callback query to switch to message handler
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("check", check_now))
    application.add_handler(conv_handler)
    application.add_handler(delete_conv_handler)
    application.add_handler(update_conv_handler)
    application.add_handler(CallbackQueryHandler(handle_notification_action, pattern="^delete_"))

    # Auto-start tracking job
    if application.job_queue:
        application.job_queue.run_repeating(check_prices, interval=1800, first=10)
        application.job_queue.run_repeating(send_heartbeat, interval=60, first=5)
        logger.info("Tracking job scheduled.")

    logger.info("Bot started. Waiting for commands...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
