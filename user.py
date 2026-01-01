"""
User management module for NEXA NET VPN Bot
Handles user interactions and status
"""
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from database import Database
from utils import format_date, get_time_until_expiry, check_channel_membership

logger = logging.getLogger(__name__)

class UserManager:
    def __init__(self, db: Database):
        self.db = db
    
    async def show_welcome(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show welcome message and menu"""
        user_id = update.effective_user.id
        username = update.effective_user.username or f"User_{user_id}"
        
        # Add/update user in database
        self.db.add_user(user_id, username)
        
        from utils import create_menu_keyboard
        
        welcome_text = (
            "🚀 **Welcome to NEXA NET VPN**\n\n"
            "🔐 **Premium VPN Configurations**\n"
            "📱 **Supported:** .hc, .ehi, .ziv, .dark, .json\n\n"
            "📋 **Requirements:**\n"
            "1. Join @nexanetofficial\n"
            "2. Make payment (KES 200 for 30 days)\n"
            "3. Download unlimited configs\n\n"
            "💳 **Payment Method:**\n"
            "M-Pesa Pochi la Biashara\n"
            "Number: `0113004884`\n\n"
            "Select an option below:"
        )
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=create_menu_keyboard(),
            parse_mode='Markdown'
        )
    
    async def show_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show main menu"""
        query = update.callback_query
        await query.answer()
        
        from utils import create_menu_keyboard
        
        await query.edit_message_text(
            "🏠 **Main Menu**\n\n"
            "Select an option:",
            reply_markup=create_menu_keyboard(),
            parse_mode='Markdown'
        )
    
    async def show_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show help information"""
        query = update.callback_query
        await query.answer()
        
        help_text = (
            "❓ **HELP & SUPPORT**\n\n"
            "**How to use this bot:**\n"
            "1. Join @nexanetofficial (mandatory)\n"
            "2. Make payment via 'Make Payment'\n"
            "3. Wait for admin approval\n"
            "4. Download configs from 'Get Configs'\n\n"
            "**Payment Issues:**\n"
            "• Ensure screenshot shows transaction details\n"
            "• Include your username in payment reference\n"
            "• Wait up to 24 hours for approval\n\n"
            "**Config Issues:**\n"
            "• Supported: .hc, .ehi, .ziv, .dark, .json\n"
            "• Configs auto-expire after 30 days\n"
            "• Unlimited downloads for active users\n\n"
            "**Support:**\n"
            "Contact @nexanetadmin for assistance"
        )
        
        from utils import create_back_button
        
        await query.edit_message_text(
            help_text,
            reply_markup=create_back_button("menu"),
            parse_mode='Markdown'
        )
    
    async def show_user_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show user status and subscription info"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if not user:
            await query.edit_message_text("❌ User not found.")
            return
        
        # Check channel membership
        channel_member = check_channel_membership(context.bot, user_id)
        channel_status = "✅ Joined" if channel_member else "❌ Not Joined"
        
        # Subscription status
        payment_status = user['payment_status']
        if payment_status == 'approved':
            if user['expiry_date']:
                expiry_status = get_time_until_expiry(user['expiry_date'])
                if expiry_status == "Expired":
                    subscription_status = "🔴 Expired"
                else:
                    subscription_status = f"🟢 Active ({expiry_status} remaining)"
            else:
                subscription_status = "🟡 Pending"
        elif payment_status == 'pending':
            subscription_status = "🟡 Payment Pending"
        else:
            subscription_status = "🔴 No Subscription"
        
        # Format dates
        join_date = format_date(user['join_date'])
        expiry_date = format_date(user['expiry_date'])
        
        status_text = (
            "📊 **YOUR STATUS**\n\n"
            f"👤 **User:** @{user['username'] or 'N/A'}\n"
            f"🆔 **ID:** `{user_id}`\n"
            f"📅 **Joined:** {join_date}\n\n"
            f"📢 **Channel:** {channel_status}\n"
            f"💳 **Subscription:** {subscription_status}\n"
            f"📅 **Expires:** {expiry_date}\n"
            f"📥 **Downloads:** {user['total_downloads']}\n\n"
        )
        
        # Add instructions based on status
        if not channel_member:
            status_text += "⚠️ **Action Required:**\nJoin @nexanetofficial to access configs\n\n"
        elif payment_status != 'approved':
            status_text += "⚠️ **Action Required:**\nMake payment to download configs\n\n"
        elif expiry_date == "Expired":
            status_text += "⚠️ **Action Required:**\nRenew your subscription\n\n"
        else:
            status_text += "✅ **Ready to download configs!**\n\n"
        
        from utils import create_back_button
        
        await query.edit_message_text(
            status_text,
            reply_markup=create_back_button("menu"),
            parse_mode='Markdown'
        )
    
    async def show_category_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show category selection for configs"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if not user:
            await query.edit_message_text("❌ User not found.")
            return
        
        # Check channel membership
        if not check_channel_membership(context.bot, user_id):
            await query.edit_message_text(
                "❌ You must join our official channel first:\n"
                "@nexanetofficial\n\n"
                "Join and try again.",
                reply_markup=self._get_back_to_menu_keyboard()
            )
            return
        
        # Check payment status
        if user['payment_status'] != 'approved':
            await query.edit_message_text(
                "❌ Payment required.\n"
                "Please complete payment approval first.",
                reply_markup=self._get_back_to_menu_keyboard()
            )
            return
        
        # Check expiry
        if user['expiry_date']:
            from datetime import datetime
            expiry = datetime.fromisoformat(user['expiry_date'])
            if expiry < datetime.now():
                await query.edit_message_text(
                    "❌ Subscription expired.\n"
                    "Please renew your payment.",
                    reply_markup=self._get_back_to_menu_keyboard()
                )
                return
        
        from utils import create_category_keyboard
        
        await query.edit_message_text(
            "📂 **SELECT CATEGORY**\n\n"
            "Choose a config category:",
            reply_markup=create_category_keyboard(),
            parse_mode='Markdown'
        )
    
    def _get_back_to_menu_keyboard(self):
        """Get back to menu keyboard"""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]]
        return InlineKeyboardMarkup(keyboard)
