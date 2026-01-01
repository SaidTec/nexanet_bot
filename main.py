"""
Main module for NEXA NET VPN Bot
Entry point and core bot setup
"""
import logging
import signal
import sys
import os
import asyncio
from datetime import datetime
from threading import Thread
import schedule
import time

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

# Import modules
from database import Database
from admin import AdminManager
from user import UserManager
from configs import ConfigManager
from payments import PaymentManager
from utils import setup_logging, ensure_directories, cleanup_temp_files

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Global instances
db = Database()
admin_manager = AdminManager(db)
user_manager = UserManager(db)
config_manager = ConfigManager(db)
payment_manager = PaymentManager(db)

# Bot token (to be set by user)
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Replace with actual token

def run_scheduled_tasks():
    """Run scheduled tasks in background thread"""
    def job_cleanup():
        """Clean up expired users and configs"""
        try:
            # Delete expired users
            expired_users = db.delete_expired_users()
            if expired_users > 0:
                logger.info(f"Cleaned up {expired_users} expired users")
            
            # Delete expired configs
            expired_configs = db.delete_expired_configs()
            if expired_configs > 0:
                logger.info(f"Cleaned up {expired_configs} expired configs")
            
            # Clean up temp files
            cleanup_temp_files()
            
        except Exception as e:
            logger.error(f"Error in scheduled job: {e}")
    
    # Schedule jobs
    schedule.every().day.at("00:00").do(job_cleanup)
    
    # Run scheduler
    while True:
        schedule.run_pending()
        time.sleep(60)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    await user_manager.show_welcome(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all messages"""
    # Check if admin is expecting broadcast
    if context.user_data.get('awaiting_broadcast'):
        from admin import AdminManager
        am = AdminManager(db)
        await am.process_broadcast(update, context)
        return
    
    # Check if admin is expecting user to expire
    if context.user_data.get('awaiting_expire_user'):
        from admin import AdminManager
        am = AdminManager(db)
        await am.process_expire_user(update, context)
        return
    
    # Check if expecting payment proof
    if context.user_data.get('awaiting_payment'):
        await payment_manager.handle_payment_proof(update, context)
        return
    
    # Check if expecting config file
    if context.user_data.get('awaiting_config'):
        await config_manager.handle_upload(update, context)
        return
    
    # Handle other messages
    if update.message.text:
        await update.message.reply_text(
            "Please use the menu buttons to navigate.",
            reply_markup=user_manager._get_back_to_menu_keyboard()
        )

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all callback queries"""
    query = update.callback_query
    data = query.data
    
    try:
        # Main menu
        if data == "menu":
            await user_manager.show_menu(update, context)
        
        # User functions
        elif data == "my_status":
            await user_manager.show_user_status(update, context)
        elif data == "help":
            await user_manager.show_help(update, context)
        
        # Payment functions
        elif data == "make_payment":
            await payment_manager.show_payment_instructions(update, context)
        
        # Config functions
        elif data == "category_select":
            await user_manager.show_category_selection(update, context)
        elif data.startswith("category_"):
            category = data.replace("category_", "")
            await config_manager.list_configs(update, context, category)
        elif data.startswith("download_"):
            config_id = int(data.replace("download_", ""))
            await config_manager.download_config(update, context, config_id)
        elif data.startswith("configs_page_"):
            # Handle pagination - currently handled in config_manager.list_configs
            pass
        
        # Admin functions
        elif data == "admin":
            await admin_manager.show_admin_panel(update, context)
        elif data == "admin_stats":
            await admin_manager.show_stats(update, context)
        elif data == "admin_users":
            await admin_manager.list_users(update, context)
        elif data.startswith("users_page_"):
            page = int(data.replace("users_page_", ""))
            context.user_data['users_page'] = page
            await admin_manager.list_users(update, context)
        elif data == "admin_payments":
            await payment_manager.list_pending_payments(update, context)
        elif data.startswith("payments_page_"):
            page = int(data.replace("payments_page_", ""))
            context.user_data['payment_page'] = page
            await payment_manager.list_pending_payments(update, context)
        elif data.startswith("review_"):
            payment_id = int(data.replace("review_", ""))
            await payment_manager.review_payment(update, context, payment_id)
        elif data.startswith("approve_"):
            payment_id = int(data.replace("approve_", ""))
            await payment_manager.approve_payment(update, context, payment_id)
        elif data.startswith("reject_"):
            payment_id = int(data.replace("reject_", ""))
            await payment_manager.reject_payment(update, context, payment_id)
        elif data == "admin_upload":
            # Show category selection for upload
            query = update.callback_query
            await query.answer()
            if admin_manager.is_admin(update.effective_user.id):
                await query.edit_message_text(
                    "📁 Select config category:",
                    reply_markup=config_manager._get_category_keyboard()
                )
        elif data.startswith("upload_category_"):
            await config_manager.handle_category_selection(update, context)
        elif data == "admin_delete_config":
            await config_manager.list_configs_for_deletion(update, context)
        elif data.startswith("delete_config_"):
            config_id = int(data.replace("delete_config_", ""))
            await config_manager.delete_config(update, context, config_id)
        elif data == "admin_broadcast":
            await admin_manager.broadcast_message(update, context)
        elif data == "admin_expire_user":
            await admin_manager.expire_user(update, context)
        
        # Unknown callback
        else:
            await query.answer("Unknown command")
            logger.warning(f"Unknown callback data: {data}")
    
    except Exception as e:
        logger.error(f"Error handling callback: {e}")
        try:
            await query.answer("❌ An error occurred. Please try again.")
        except:
            pass

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command"""
    # Clear any pending states
    for key in ['awaiting_payment', 'awaiting_config', 'awaiting_broadcast', 'awaiting_expire_user']:
        context.user_data.pop(key, None)
    
    await update.message.reply_text(
        "Operation cancelled.",
        reply_markup=user_manager._get_back_to_menu_keyboard()
    )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin command"""
    if admin_manager.is_admin(update.effective_user.id):
        await admin_manager.show_admin_panel(update, context)
    else:
        await update.message.reply_text("❌ Unauthorized.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    await user_manager.show_user_status(update, context)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    
    try:
        if update and update.effective_user:
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text="❌ An error occurred. Please try again."
            )
    except:
        pass

def main():
    """Main function to start the bot"""
    # Ensure directories exist
    ensure_directories()
    
    # Start scheduled tasks in background thread
    scheduler_thread = Thread(target=run_scheduled_tasks, daemon=True)
    scheduler_thread.start()
    
    # Create Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("cancel", cancel))
    
    # Callback query handler
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_message))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Start polling
    logger.info("Starting NEXA NET VPN Bot...")
    print("=" * 50)
    print("NEXA NET VPN Bot Started Successfully!")
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Admin ID: 7108127485 (@nexanetadmin)")
    print(f"Channel: @nexanetofficial")
    print(f"Bot: @nexanetofficial_bot")
    print("=" * 50)
    print("Bot is running. Press Ctrl+C to stop.")
    print("To run in background: nohup python main.py &")
    print("=" * 50)
    
    # Run bot until stopped
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    # Signal handling for graceful shutdown
    def signal_handler(signum, frame):
        logger.info("Shutdown signal received. Stopping bot...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Check for bot token
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: Bot token not set!")
        print("Please edit main.py and replace BOT_TOKEN with your actual bot token.")
        print("Get token from @BotFather on Telegram.")
        sys.exit(1)
    
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
