"""
Admin module for NEXA NET VPN Bot
Handles admin-only functions
"""
import logging
from datetime import datetime
from typing import List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import Database
from utils import format_date, format_bytes, get_time_until_expiry

logger = logging.getLogger(__name__)

class AdminManager:
    def __init__(self, db: Database):
        self.db = db
        self.admin_id = 7108127485
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        if user_id == self.admin_id:
            return True
        
        user = self.db.get_user(user_id)
        return user and user.get('is_admin', 0) == 1
    
    async def show_admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show admin panel"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_admin(update.effective_user.id):
            await query.edit_message_text("❌ Unauthorized.")
            return
        
        from utils import create_admin_keyboard
        
        await query.edit_message_text(
            "🛠️ **ADMIN PANEL**\n\n"
            "Select an option:",
            reply_markup=create_admin_keyboard(),
            parse_mode='Markdown'
        )
    
    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show system statistics"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_admin(update.effective_user.id):
            await query.edit_message_text("❌ Unauthorized.")
            return
        
        stats = self.db.get_stats()
        
        message_text = (
            "📊 **SYSTEM STATISTICS**\n\n"
            f"👥 **Users:**\n"
            f"• Total: {stats['total_users']}\n"
            f"• Active: {stats['active_users']}\n\n"
            f"📁 **Configs:**\n"
            f"• Total: {stats['total_configs']}\n\n"
            f"📥 **Downloads:**\n"
            f"• Total: {stats['total_downloads']}\n"
            f"• Today: {stats['today_downloads']}\n\n"
            f"💳 **Payments:**\n"
            f"• Pending: {stats['pending_payments']}\n\n"
            f"🕐 Last updated: {datetime.now().strftime('%H:%M:%S')}"
        )
        
        keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="admin_stats"),
                     InlineKeyboardButton("⬅️ Back", callback_data="admin")]]
        
        await query.edit_message_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def list_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """List all users"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_admin(update.effective_user.id):
            await query.edit_message_text("❌ Unauthorized.")
            return
        
        users = self.db.get_all_users()
        
        # Pagination
        page = context.user_data.get('users_page', 0)
        users_per_page = 10
        start_idx = page * users_per_page
        end_idx = start_idx + users_per_page
        current_users = users[start_idx:end_idx]
        
        message_text = f"👥 **ALL USERS**\n\n"
        message_text += f"Total users: {len(users)}\n"
        message_text += f"Page: {page + 1}/{(len(users) + users_per_page - 1) // users_per_page}\n\n"
        
        for i, user in enumerate(current_users, start=start_idx + 1):
            status = "🟢" if user['payment_status'] == 'approved' else "🟡" if user['payment_status'] == 'pending' else "🔴"
            username = f"@{user['username']}" if user['username'] else f"User_{user['user_id']}"
            
            if user['expiry_date']:
                expiry_status = get_time_until_expiry(user['expiry_date'])
                if expiry_status == "Expired":
                    status = "🔴"
            else:
                expiry_status = "Never"
            
            admin_badge = " 👑" if user.get('is_admin') else ""
            
            message_text += (
                f"{i}. {status} {username}{admin_badge}\n"
                f"   ID: `{user['user_id']}` | 📥: {user['total_downloads']}\n"
                f"   Status: {user['payment_status']} | Expires: {expiry_status}\n\n"
            )
        
        # Navigation buttons
        keyboard = []
        nav_buttons = []
        
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"users_page_{page-1}"))
        
        if end_idx < len(users):
            nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"users_page_{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([
            InlineKeyboardButton("🔄 Refresh", callback_data="admin_users"),
            InlineKeyboardButton("⬅️ Back", callback_data="admin")
        ])
        
        await query.edit_message_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def broadcast_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start broadcast message process"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_admin(update.effective_user.id):
            await query.edit_message_text("❌ Unauthorized.")
            return
        
        context.user_data['awaiting_broadcast'] = True
        
        await query.edit_message_text(
            "📢 **BROADCAST MESSAGE**\n\n"
            "Please send the message you want to broadcast to all users.\n"
            "You can include text, photos, or documents.\n\n"
            "Type /cancel to cancel.",
            reply_markup=self._get_cancel_keyboard()
        )
    
    async def process_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process broadcast message"""
        if not self.is_admin(update.effective_user.id):
            return
        
        if not context.user_data.get('awaiting_broadcast', False):
            return
        
        users = self.db.get_all_users()
        successful = 0
        failed = 0
        
        # Send to all users
        for user in users:
            try:
                # Forward the message
                if update.message.text:
                    await context.bot.send_message(
                        chat_id=user['user_id'],
                        text=update.message.text
                    )
                elif update.message.photo:
                    await context.bot.send_photo(
                        chat_id=user['user_id'],
                        photo=update.message.photo[-1].file_id,
                        caption=update.message.caption or ""
                    )
                elif update.message.document:
                    await context.bot.send_document(
                        chat_id=user['user_id'],
                        document=update.message.document.file_id,
                        caption=update.message.caption or ""
                    )
                successful += 1
            except Exception as e:
                logger.error(f"Failed to send to user {user['user_id']}: {e}")
                failed += 1
        
        # Clear state
        context.user_data.pop('awaiting_broadcast', None)
        
        await update.message.reply_text(
            f"📢 **BROADCAST COMPLETE**\n\n"
            f"✅ Successful: {successful}\n"
            f"❌ Failed: {failed}\n"
            f"📊 Total: {len(users)}",
            reply_markup=self._get_back_to_admin_keyboard()
        )
    
    async def expire_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Manually expire a user"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_admin(update.effective_user.id):
            await query.edit_message_text("❌ Unauthorized.")
            return
        
        context.user_data['awaiting_expire_user'] = True
        
        await query.edit_message_text(
            "⏰ **EXPIRE USER**\n\n"
            "Please send the User ID to expire immediately.\n"
            "You can get User ID from View Users.\n\n"
            "Type /cancel to cancel.",
            reply_markup=self._get_cancel_keyboard()
        )
    
    async def process_expire_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process user expiry"""
        if not self.is_admin(update.effective_user.id):
            return
        
        if not context.user_data.get('awaiting_expire_user', False):
            return
        
        try:
            user_id = int(update.message.text)
            user = self.db.get_user(user_id)
            
            if not user:
                await update.message.reply_text("❌ User not found.")
                return
            
            # Set expiry to past
            from datetime import datetime, timedelta
            expired_date = (datetime.now() - timedelta(days=1)).isoformat()
            
            # Update in database
            import sqlite3
            conn = sqlite3.connect("data/nexa_net.db")
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE users SET expiry_date = ? WHERE user_id = ?',
                (expired_date, user_id)
            )
            conn.commit()
            conn.close()
            
            # Clear state
            context.user_data.pop('awaiting_expire_user', None)
            
            username = f"@{user['username']}" if user['username'] else f"User_{user_id}"
            await update.message.reply_text(
                f"✅ User {username} has been expired.\n"
                f"They will lose access immediately.",
                reply_markup=self._get_back_to_admin_keyboard()
            )
            
        except ValueError:
            await update.message.reply_text("❌ Invalid User ID. Please enter a number.")
        except Exception as e:
            logger.error(f"Error expiring user: {e}")
            await update.message.reply_text("❌ Error expiring user.")
    
    def _get_back_to_admin_keyboard(self) -> InlineKeyboardMarkup:
        """Get back to admin keyboard"""
        keyboard = [[InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin")]]
        return InlineKeyboardMarkup(keyboard)
    
    def _get_cancel_keyboard(self) -> InlineKeyboardMarkup:
        """Get cancel keyboard"""
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin")]]
        return InlineKeyboardMarkup(keyboard)
