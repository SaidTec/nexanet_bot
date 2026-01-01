"""
Config management module for NEXA NET VPN Bot
Handles config upload, storage, and download
"""
import os
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackContext

from database import Database
from utils import ConfigEncryptor, is_valid_config_extension, generate_filename

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self, db: Database):
        self.db = db
        self.encryptor = ConfigEncryptor()
    
    async def handle_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle config file upload from admin"""
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        # Check if user is admin
        if not user or not user.get('is_admin'):
            await update.message.reply_text("❌ Unauthorized. Admin access required.")
            return
        
        # Check if we're expecting a file
        if 'awaiting_config' not in context.user_data:
            await update.message.reply_text(
                "Please select config category first:",
                reply_markup=self._get_category_keyboard()
            )
            return
        
        document = update.message.document
        if not document:
            await update.message.reply_text("❌ Please send a config file.")
            return
        
        # Validate file extension
        filename = document.file_name
        if not is_valid_config_extension(filename):
            await update.message.reply_text(
                "❌ Invalid file type. Allowed extensions: .hc, .ehi, .ziv, .dark, .json"
            )
            return
        
        # Get category from context
        category = context.user_data.get('awaiting_config')
        
        try:
            # Download file
            file = await document.get_file()
            temp_path = f"temp/{int(datetime.now().timestamp())}_{filename}"
            await file.download_to_drive(temp_path)
            
            # Generate encrypted filename
            encrypted_filename = generate_filename(filename, user_id)
            encrypted_path = f"configs/{encrypted_filename}"
            
            # Encrypt and save
            if self.encryptor.encrypt_file(temp_path, encrypted_path):
                # Add to database
                file_size = os.path.getsize(temp_path)
                config_id = self.db.add_config(
                    filename=encrypted_filename,
                    original_filename=filename,
                    category=category,
                    file_size=file_size,
                    expiry_days=30
                )
                
                if config_id > 0:
                    # Clean up
                    os.remove(temp_path)
                    del context.user_data['awaiting_config']
                    
                    await update.message.reply_text(
                        f"✅ Config uploaded successfully!\n"
                        f"📁 File: {filename}\n"
                        f"📂 Category: {category}\n"
                        f"🆔 Config ID: {config_id}\n"
                        f"🔒 Stored as: {encrypted_filename}",
                        reply_markup=self._get_back_to_admin_keyboard()
                    )
                else:
                    await update.message.reply_text("❌ Failed to save config to database.")
            else:
                await update.message.reply_text("❌ Failed to encrypt config file.")
            
        except Exception as e:
            logger.error(f"Error uploading config: {e}")
            await update.message.reply_text("❌ Error uploading config. Please try again.")
    
    async def handle_category_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle config category selection for upload"""
        query = update.callback_query
        await query.answer()
        
        category = query.data.replace("upload_category_", "")
        context.user_data['awaiting_config'] = category
        
        await query.edit_message_text(
            f"📁 Selected category: {category}\n"
            f"Please send the config file now.\n\n"
            f"⚠️ Supported formats: .hc, .ehi, .ziv, .dark, .json"
        )
    
    async def list_configs(self, update: Update, context: ContextTypes.DEFAULT_TYPE, category: str) -> None:
        """List configs for a category"""
        query = update.callback_query
        await query.answer()
        
        configs = self.db.get_configs_by_category(category)
        
        if not configs:
            await query.edit_message_text(
                f"📭 No configs available for {category}.\n"
                f"Please check back later.",
                reply_markup=self._get_back_to_categories_keyboard()
            )
            return
        
        from utils import create_configs_keyboard
        keyboard, current_page = create_configs_keyboard(configs)
        
        await query.edit_message_text(
            f"📂 {category} Configs\n"
            f"📊 Total: {len(configs)}\n"
            f"📄 Page: {current_page}\n\n"
            f"Select a config to download:",
            reply_markup=keyboard
        )
    
    async def download_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE, config_id: int) -> None:
        """Handle config download"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        # Check if user exists
        if not user:
            await query.edit_message_text(
                "❌ User not found. Please start the bot with /start",
                reply_markup=self._get_back_to_menu_keyboard()
            )
            return
        
        # Check channel membership
        from utils import check_channel_membership
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
            expiry = datetime.fromisoformat(user['expiry_date'])
            if expiry < datetime.now():
                await query.edit_message_text(
                    "❌ Subscription expired.\n"
                    "Please renew your payment.",
                    reply_markup=self._get_back_to_menu_keyboard()
                )
                return
        
        # Get config
        config = self.db.get_config(config_id)
        if not config or config.get('is_active', 0) == 0:
            await query.edit_message_text(
                "❌ Config not found or expired.",
                reply_markup=self._get_back_to_menu_keyboard()
            )
            return
        
        try:
            # Prepare download
            encrypted_path = f"configs/{config['filename']}"
            temp_decrypted_path = f"temp/{int(datetime.now().timestamp())}_{config['original_filename']}"
            
            # Decrypt config
            if self.encryptor.decrypt_file(encrypted_path, temp_decrypted_path):
                # Send file
                with open(temp_decrypted_path, 'rb') as file:
                    await context.bot.send_document(
                        chat_id=user_id,
                        document=file,
                        filename=config['original_filename'],
                        caption=f"📥 {config['original_filename']}\n"
                               f"📂 Category: {config['category']}\n"
                               f"📊 Downloads: {config['total_downloads'] + 1}\n\n"
                               f"Enjoy your VPN! 🚀"
                    )
                
                # Record download
                self.db.record_download(user_id, config_id)
                self.db.increment_downloads(user_id)
                
                # Clean up
                os.remove(temp_decrypted_path)
                
                # Update message
                await query.edit_message_text(
                    f"✅ Config downloaded successfully!\n"
                    f"📁 File: {config['original_filename']}\n"
                    f"📂 Category: {config['category']}",
                    reply_markup=self._get_back_to_categories_keyboard()
                )
            else:
                await query.edit_message_text(
                    "❌ Error decrypting config.",
                    reply_markup=self._get_back_to_menu_keyboard()
                )
                
        except Exception as e:
            logger.error(f"Error downloading config: {e}")
            await query.edit_message_text(
                "❌ Error downloading config. Please try again.",
                reply_markup=self._get_back_to_menu_keyboard()
            )
    
    async def delete_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE, config_id: int) -> None:
        """Delete config (admin only)"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if not user or not user.get('is_admin'):
            await query.edit_message_text("❌ Unauthorized.")
            return
        
        config = self.db.get_config(config_id)
        if not config:
            await query.edit_message_text("❌ Config not found.")
            return
        
        # Delete file
        filepath = f"configs/{config['filename']}"
        if os.path.exists(filepath):
            os.remove(filepath)
        
        # Delete from database
        if self.db.delete_config(config_id):
            await query.edit_message_text(
                f"✅ Config deleted successfully!\n"
                f"📁 File: {config['original_filename']}",
                reply_markup=self._get_back_to_admin_keyboard()
            )
        else:
            await query.edit_message_text(
                "❌ Failed to delete config from database.",
                reply_markup=self._get_back_to_admin_keyboard()
            )
    
    async def list_configs_for_deletion(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """List configs for deletion (admin)"""
        query = update.callback_query
        await query.answer()
        
        configs = self.db.get_all_configs()
        
        if not configs:
            await query.edit_message_text(
                "📭 No configs available.",
                reply_markup=self._get_back_to_admin_keyboard()
            )
            return
        
        keyboard = []
        for config in configs[:20]:  # Limit to 20 for inline keyboard
            filename = config['original_filename']
            if len(filename) > 25:
                filename = filename[:22] + "..."
            button_text = f"🗑️ {filename} ({config['category']})"
            keyboard.append([
                InlineKeyboardButton(
                    button_text, 
                    callback_data=f"delete_config_{config['config_id']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin")])
        
        await query.edit_message_text(
            f"🗑️ Delete Configs\n"
            f"📊 Total configs: {len(configs)}\n\n"
            f"Select a config to delete:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    def _get_category_keyboard(self) -> InlineKeyboardMarkup:
        """Get category keyboard for upload"""
        keyboard = [
            [
                InlineKeyboardButton("Safaricom", callback_data="upload_category_Safaricom"),
                InlineKeyboardButton("Airtel", callback_data="upload_category_Airtel")
            ],
            [
                InlineKeyboardButton("Telkom", callback_data="upload_category_Telkom"),
                InlineKeyboardButton("Other", callback_data="upload_category_Other")
            ],
            [
                InlineKeyboardButton("Cancel", callback_data="admin")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def _get_back_to_admin_keyboard(self) -> InlineKeyboardMarkup:
        """Get back to admin keyboard"""
        keyboard = [[InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin")]]
        return InlineKeyboardMarkup(keyboard)
    
    def _get_back_to_categories_keyboard(self) -> InlineKeyboardMarkup:
        """Get back to categories keyboard"""
        keyboard = [[InlineKeyboardButton("⬅️ Back to Categories", callback_data="category_select")]]
        return InlineKeyboardMarkup(keyboard)
    
    def _get_back_to_menu_keyboard(self) -> InlineKeyboardMarkup:
        """Get back to menu keyboard"""
        keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]]
        return InlineKeyboardMarkup(keyboard)
