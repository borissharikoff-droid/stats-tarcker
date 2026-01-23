import asyncio
import logging
import io
from datetime import datetime

import telegram
from telegram import Update, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import config
from scraper import fetch_statistics, format_stats_message, generate_charts
from storage import stats_to_dict, load_previous_stats, save_current_stats, get_diffs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def send_stats_to_telegram(bot: telegram.Bot, chat_id: str) -> bool:
    """
    Fetch statistics and send them to Telegram chat with charts.
    
    Args:
        bot: Telegram Bot instance
        chat_id: Target chat ID
        
    Returns:
        True if message sent successfully, False otherwise
    """
    try:
        logger.info("Fetching statistics from website...")
        
        # Fetch statistics (this is synchronous, run in executor)
        loop = asyncio.get_event_loop()
        stats_data = await loop.run_in_executor(None, fetch_statistics)
        
        if stats_data.error:
            # Send error message
            message = format_stats_message(stats_data)
            await bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
            return False
        
        # Convert to dict for storage/comparison
        current_stats = stats_to_dict(stats_data)
        
        # Load previous stats and calculate diffs
        previous_stats = load_previous_stats()
        diffs = get_diffs(current_stats, previous_stats)
        
        # Save current stats for next comparison
        save_current_stats(current_stats)
        
        # Format message with diffs
        message = format_stats_message(stats_data, diffs)
        
        logger.info(f"Sending message to chat {chat_id}")
        logger.debug(f"Message content: {message}")
        
        # Generate charts
        logger.info("Generating charts...")
        charts = await loop.run_in_executor(None, generate_charts, stats_data)
        
        # Send text message first
        await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode=ParseMode.HTML
        )
        
        # Send charts as photos
        if charts:
            logger.info(f"Sending {len(charts)} charts...")
            media_group = []
            for chart_name, chart_bytes in charts:
                media_group.append(
                    InputMediaPhoto(
                        media=io.BytesIO(chart_bytes),
                        caption=chart_name
                    )
                )
            
            if media_group:
                await bot.send_media_group(
                    chat_id=chat_id,
                    media=media_group
                )
        
        logger.info("Message and charts sent successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send stats: {e}")
        
        # Try to send error notification
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=f"<b>Ошибка</b>: не удалось получить статистику\n{str(e)}\n\n\n#Report",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
        
        return False


async def scheduled_job(bot: telegram.Bot, chat_id: str):
    """Job function to be called by scheduler."""
    logger.info(f"Running scheduled job at {datetime.now()}")
    await send_stats_to_telegram(bot, chat_id)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    
    message = (
        f"<b>Бот статистики запущен</b>\n\n"
        f"<b>Chat ID</b>: <code>{chat_id}</code>\n"
        f"<b>Тип чата</b>: {chat_type}\n\n"
        f"Добавьте этот Chat ID в переменную окружения TELEGRAM_CHAT_ID для получения автоматических отчетов."
    )
    
    await update.message.reply_text(message, parse_mode=ParseMode.HTML)
    logger.info(f"Start command received. Chat ID: {chat_id}, Type: {chat_type}")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command - send statistics immediately."""
    chat_id = update.effective_chat.id
    
    await update.message.reply_text("Загрузка статистики...", parse_mode=ParseMode.HTML)
    
    # Fetch and send stats
    await send_stats_to_telegram(context.bot, str(chat_id))


async def chatid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /chatid command - show current chat ID."""
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    chat_title = update.effective_chat.title or "Private"
    
    message = (
        f"<b>Информация о чате</b>\n\n"
        f"<b>Chat ID</b>: <code>{chat_id}</code>\n"
        f"<b>Тип</b>: {chat_type}\n"
        f"<b>Название</b>: {chat_title}"
    )
    
    await update.message.reply_text(message, parse_mode=ParseMode.HTML)


async def main():
    """Main function to run the bot."""
    # Validate configuration
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set!")
        return
    
    if not config.STATS_LOGIN or not config.STATS_PASSWORD:
        logger.error("STATS_LOGIN or STATS_PASSWORD is not set!")
        return
    
    logger.info("Initializing Telegram bot...")
    
    # Create Application
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("chatid", chatid_command))
    
    # Test bot connection
    try:
        bot_info = await application.bot.get_me()
        logger.info(f"Bot initialized: @{bot_info.username}")
    except Exception as e:
        logger.error(f"Failed to connect to Telegram: {e}")
        return
    
    # Initialize scheduler if CHAT_ID is set
    scheduler = None
    if config.TELEGRAM_CHAT_ID:
        logger.info("Initializing scheduler...")
        scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)
        
        # Add jobs for each scheduled hour
        for hour in config.SCHEDULE_HOURS:
            trigger = CronTrigger(hour=hour, minute=0, timezone=config.TIMEZONE)
            scheduler.add_job(
                scheduled_job,
                trigger=trigger,
                args=[application.bot, config.TELEGRAM_CHAT_ID],
                id=f"stats_job_{hour}",
                name=f"Send stats at {hour:02d}:00",
                replace_existing=True
            )
            logger.info(f"Scheduled job at {hour:02d}:00 {config.TIMEZONE}")
        
        # Start scheduler
        scheduler.start()
        logger.info("Scheduler started!")
        
        # Send initial stats on startup
        logger.info("Sending initial stats message...")
        await send_stats_to_telegram(application.bot, config.TELEGRAM_CHAT_ID)
    else:
        logger.warning("TELEGRAM_CHAT_ID is not set! Scheduler disabled.")
        logger.info("Use /start or /chatid command in your group to get the Chat ID.")
    
    # Start the bot
    logger.info("Bot is running. Press Ctrl+C to stop.")
    
    # Run the bot
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
    finally:
        if scheduler:
            scheduler.shutdown()
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
