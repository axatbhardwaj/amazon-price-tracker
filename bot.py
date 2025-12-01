import logging
import os
import asyncio
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from tracker import load_items, save_history, load_history, process_item, ITEMS_FILE, setup_logging
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Enable logging
setup_logging()
logger = logging.getLogger(__name__)

# States for ConversationHandler
LINK, NAME, PLATFORM, THRESHOLD = range(4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks for the link."""
    await update.message.reply_text(
        "Hi! I'm your Price Tracker Bot.\n"
        "Send /add to start tracking a new item.\n"
        "Send /check to check prices immediately.\n"
        "Send /cancel to stop the current operation."
    )
    return ConversationHandler.END

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the add item conversation."""
    await update.message.reply_text(
        "Let's track a new item! First, please send me the product link."
    )
    return LINK

async def link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the link and asks for the name."""
    context.user_data["url"] = update.message.text
    await update.message.reply_text(
        "Got it! Now, what should I call this item?"
    )
    return NAME

async def name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the name and asks for the platform."""
    context.user_data["name"] = update.message.text
    
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
            
        async def item_notification_callback(title, message, item_url=None):
            text = f"{title}\n{message}"
            if item_url:
                text += f"\n\nLink: {item_url}"
            try:
                await app.bot.send_message(chat_id=user_id, text=text)
            except Exception as e:
                logger.error(f"Failed to send message to {user_id}: {e}")

        # Using run_in_executor to avoid blocking the bot
        await loop.run_in_executor(
            None, 
            lambda i=item: process_item(i, history, lambda t, m, u: asyncio.run_coroutine_threadsafe(item_notification_callback(t, m, u), loop))
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

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check", check_now))
    application.add_handler(conv_handler)

    # Auto-start tracking job
    if application.job_queue:
        application.job_queue.run_repeating(check_prices, interval=1800, first=10)
        logger.info("Tracking job scheduled.")

    logger.info("Bot started. Waiting for commands...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
