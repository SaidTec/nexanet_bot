"""
Payment handling module for NEXA NET VPN Bot
Handles payment submission and approval
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import Database
from utils import format_date, format_bytes

logger = logging.getLogger(__name__)

class PaymentManager:
    def __init__(self, db: Database):
        self.db = db
        self.payment_info = {
            'method': 'M-Pesa Pochi la Biashara',
            'number': '0113004884',
            'amount': 'KES 200',
            'duration': '30 days'
        }
    
    async def show_payment_instructions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show payment instructions to user"""
        query = update.callback_query
        await query.answer()
        
        instructions = (
            "💳 **PAYMENT INSTRUCTIONS**\n\n"
            f"**Method:** {self.payment_info['method']}\n"
            f"**Number:** `{self.payment_info['number']}`\n"
            f"**Amount:** {self.payment_info['amount']}\n"
            f"**Duration:** {self.payment_info['duration']}\n\n"
            "**Steps to complete payment:**\n"
            "1. Send KES 200 to the number above\n"
            "2. Take a CLEAR screenshot of payment confirmation\n"
            "3. Send the screenshot to this bot\n"
            "4. Wait for admin approval (usually within 24 hours)\n\n"
            "⚠️ **Important Notes:**\n"
            "• Include your username in payment reference\n"
            "• Screenshot must show transaction details\n"
            "• Do not edit or crop the screenshot\n\n"
            "Send your payment screenshot now:"
        )
        
        keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu")]]
        
        if query.message:
            await query.edit_message_text(
                instructions,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text=instructions,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        # Set state to expect payment proof
        context.user_data['awaiting_payment'] = True
    
    async def handle_payment_proof(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle payment proof submission"""
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if not user:
            await update.message.reply_text(
                "❌ User not found. Please start the bot with /start",
                reply_markup=self._get_back_to_menu_keyboard()
            )
            return
        
        # Check if we're expecting payment proof
        if not context.user_data.get('awaiting_payment', False):
            await update.message.reply_text(
                "Please use the menu to make a payment.",
                reply_markup=self._get_back_to_menu_keyboard()
            )
            return
        
        # Check for photo or document
        photo = update.message.photo
        document = update.message.document
        
        if not photo and not document:
            await update.message.reply_text(
                "❌ Please send a screenshot/image of your payment confirmation.",
                reply_markup=self._get_back_to_menu_keyboard()
            )
            return
        
        try:
            # Save payment proof
            timestamp = int(datetime.now().timestamp())
            proof_filename = f"payments/payment_{user_id}_{timestamp}.jpg"
            
            if photo:
                # Get the largest photo
                file = await photo[-1].get_file()
            else:
                # Get document
                file = await document.get_file()
            
            await file.download_to_drive(proof_filename)
            
            # Add payment record
            payment_id = self.db.add_payment(
                user_id=user_id,
                amount=200.0,
                proof_path=proof_filename
            )
            
            if payment_id > 0:
                # Update user payment status
                self.db.update_payment_status(user_id, 'pending')
                
                # Notify admin
                await self._notify_admin(context.bot, user_id, user['username'], payment_id)
                
                # Clear state
                context.user_data.pop('awaiting_payment', None)
                
                await update.message.reply_text(
                    "✅ Payment proof received!\n\n"
                    "Your payment is pending approval.\n"
                    "You will be notified once approved.\n\n"
                    "Approval usually takes up to 24 hours.",
                    reply_markup=self._get_back_to_menu_keyboard()
                )
            else:
                await update.message.reply_text(
                    "❌ Failed to record payment. Please try again.",
                    reply_markup=self._get_back_to_menu_keyboard()
                )
                
        except Exception as e:
            logger.error(f"Error handling payment proof: {e}")
            await update.message.reply_text(
                "❌ Error processing payment proof. Please try again.",
                reply_markup=self._get_back_to_menu_keyboard()
            )
    
    async def _notify_admin(self, bot, user_id: int, username: str, payment_id: int):
        """Notify admin about new payment"""
        try:
            admin_id = 7108127485
            
            # Get payment proof path
            payment = self._get_payment_by_id(payment_id)
            if not payment:
                return
            
            proof_path = payment['payment_proof']
            
            # Send notification with inline buttons
            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve_{payment_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_{payment_id}")
                ]
            ]
            
            message_text = (
                "🆕 **NEW PAYMENT FOR APPROVAL**\n\n"
                f"**User:** @{username}\n"
                f"**User ID:** `{user_id}`\n"
                f"**Amount:** KES 200\n"
                f"**Date:** {format_date(payment['payment_date'])}\n"
                f"**Payment ID:** {payment_id}"
            )
            
            # Send photo if exists
            if os.path.exists(proof_path):
                with open(proof_path, 'rb') as photo:
                    await bot.send_photo(
                        chat_id=admin_id,
                        photo=photo,
                        caption=message_text,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
            else:
                await bot.send_message(
                    chat_id=admin_id,
                    text=message_text + "\n\n⚠️ Proof file not found",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Error notifying admin: {e}")
    
    async def list_pending_payments(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """List pending payments for admin"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if not user or not user.get('is_admin'):
            await query.edit_message_text("❌ Unauthorized.")
            return
        
        payments = self.db.get_pending_payments()
        
        if not payments:
            await query.edit_message_text(
                "📭 No pending payments.",
                reply_markup=self._get_back_to_admin_keyboard()
            )
            return
        
        # Create paginated list
        page = context.user_data.get('payment_page', 0)
        payments_per_page = 5
        start_idx = page * payments_per_page
        end_idx = start_idx + payments_per_page
        current_payments = payments[start_idx:end_idx]
        
        message_text = f"⏳ **PENDING PAYMENTS**\n\n"
        message_text += f"Total pending: {len(payments)}\n"
        message_text += f"Page: {page + 1}/{(len(payments) + payments_per_page - 1) // payments_per_page}\n\n"
        
        keyboard = []
        for payment in current_payments:
            payment_id = payment['payment_id']
            username = payment['username'] or f"User_{payment['user_id']}"
            date_str = format_date(payment['payment_date'])
            
            message_text += f"**{payment_id}.** @{username} - {date_str}\n"
            
            keyboard.append([
                InlineKeyboardButton(f"Review #{payment_id}", callback_data=f"review_{payment_id}")
            ])
        
        # Navigation buttons
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"payments_page_{page-1}"))
        
        if end_idx < len(payments):
            nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"payments_page_{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin")])
        
        await query.edit_message_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def review_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE, payment_id: int) -> None:
        """Review specific payment"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if not user or not user.get('is_admin'):
            await query.edit_message_text("❌ Unauthorized.")
            return
        
        payment = self._get_payment_by_id(payment_id)
        if not payment:
            await query.edit_message_text("❌ Payment not found.")
            return
        
        user_info = self.db.get_user(payment['user_id'])
        username = user_info['username'] if user_info else f"User_{payment['user_id']}"
        
        message_text = (
            "📋 **PAYMENT REVIEW**\n\n"
            f"**Payment ID:** {payment_id}\n"
            f"**User:** @{username}\n"
            f"**User ID:** `{payment['user_id']}`\n"
            f"**Amount:** KES {payment['amount']}\n"
            f"**Date:** {format_date(payment['payment_date'])}\n"
            f"**Status:** {payment['status'].upper()}"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{payment_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{payment_id}")
            ],
            [
                InlineKeyboardButton("⬅️ Back to Payments", callback_data="admin_payments")
            ]
        ]
        
        # Send with proof if available
        proof_path = payment['payment_proof']
        if os.path.exists(proof_path):
            with open(proof_path, 'rb') as photo:
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=photo,
                    caption=message_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            await query.delete_message()
        else:
            await query.edit_message_text(
                message_text + "\n\n⚠️ Proof file not found",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    async def approve_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE, payment_id: int) -> None:
        """Approve payment"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if not user or not user.get('is_admin'):
            await query.edit_message_text("❌ Unauthorized.")
            return
        
        payment = self._get_payment_by_id(payment_id)
        if not payment:
            await query.edit_message_text("❌ Payment not found.")
            return
        
        # Update payment status
        self.db.update_payment(payment_id, 'approved', 'Approved by admin')
        
        # Update user expiry
        self.db.update_user_expiry(payment['user_id'], days=30)
        
        # Notify user
        await self._notify_user_approval(context.bot, payment['user_id'])
        
        await query.edit_message_text(
            f"✅ Payment #{payment_id} approved!\n"
            f"User subscription extended by 30 days.",
            reply_markup=self._get_back_to_admin_keyboard()
        )
    
    async def reject_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE, payment_id: int) -> None:
        """Reject payment"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if not user or not user.get('is_admin'):
            await query.edit_message_text("❌ Unauthorized.")
            return
        
        payment = self._get_payment_by_id(payment_id)
        if not payment:
            await query.edit_message_text("❌ Payment not found.")
            return
        
        # Update payment status
        self.db.update_payment(payment_id, 'rejected', 'Rejected by admin')
        
        # Update user payment status
        self.db.update_payment_status(payment['user_id'], 'rejected')
        
        # Notify user
        await self._notify_user_rejection(context.bot, payment['user_id'])
        
        await query.edit_message_text(
            f"❌ Payment #{payment_id} rejected.\n"
            f"User has been notified.",
            reply_markup=self._get_back_to_admin_keyboard()
        )
    
    async def _notify_user_approval(self, bot, user_id: int):
        """Notify user about payment approval"""
        try:
            user = self.db.get_user(user_id)
            if not user:
                return
            
            expiry = format_date(user['expiry_date'])
            
            await bot.send_message(
                chat_id=user_id,
                text=(
                    "🎉 **PAYMENT APPROVED!**\n\n"
                    "Your payment has been approved.\n"
                    "You now have access to all configs!\n\n"
                    "✅ **Subscription Details:**\n"
                    f"• Status: Active\n"
                    f"• Expiry: {expiry}\n"
                    f"• Downloads: {user['total_downloads']}\n\n"
                    "Click 'Get Configs' to start downloading. 🚀"
                ),
                reply_markup=self._get_back_to_menu_keyboard()
            )
        except Exception as e:
            logger.error(f"Error notifying user approval: {e}")
    
    async def _notify_user_rejection(self, bot, user_id: int):
        """Notify user about payment rejection"""
        try:
            await bot.send_message(
                chat_id=user_id,
                text=(
                    "❌ **PAYMENT REJECTED**\n\n"
                    "Your payment proof was rejected.\n"
                    "Possible reasons:\n"
                    "• Unclear screenshot\n"
                    "• Incorrect amount\n"
                    "• Invalid transaction\n\n"
                    "Please submit a new payment with clear proof."
                ),
                reply_markup=self._get_back_to_menu_keyboard()
            )
        except Exception as e:
            logger.error(f"Error notifying user rejection: {e}")
    
    def _get_payment_by_id(self, payment_id: int) -> Optional[Dict]:
        """Get payment by ID from database"""
        # Since we don't have direct method in Database class, we'll filter
        payments = self.db.get_pending_payments()
        for payment in payments:
            if payment['payment_id'] == payment_id:
                return payment
        
        # Check all payments by querying database directly
        try:
            import sqlite3
            conn = sqlite3.connect("data/nexa_net.db")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM payments WHERE payment_id = ?', (payment_id,))
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
        except:
            return None
    
    def _get_back_to_admin_keyboard(self) -> InlineKeyboardMarkup:
        """Get back to admin keyboard"""
        keyboard = [[InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin")]]
        return InlineKeyboardMarkup(keyboard)
    
    def _get_back_to_menu_keyboard(self) -> InlineKeyboardMarkup:
        """Get back to menu keyboard"""
        keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]]
        return InlineKeyboardMarkup(keyboard)
