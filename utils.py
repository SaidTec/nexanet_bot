# utils_simple.py - Simplified version using pycryptodome
import logging
import os
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
import base64
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

class ConfigEncryptor:
    """Handle AES encryption/decryption for config files using pycryptodome"""
    
    def __init__(self, password: str = "nexanet-secure-key-2024"):
        """Initialize encryptor with password-derived key"""
        # Derive key from password using PBKDF2
        salt = b'nexanet_salt_123'
        key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000, 32)
        self.key = key
    
    def encrypt_file(self, input_path: str, output_path: str):
        """Encrypt file and save to output path"""
        try:
            with open(input_path, 'rb') as f:
                data = f.read()
            
            # Generate random IV
            iv = get_random_bytes(AES.block_size)
            cipher = AES.new(self.key, AES.MODE_CBC, iv)
            
            # Pad data and encrypt
            padded_data = pad(data, AES.block_size)
            encrypted_data = iv + cipher.encrypt(padded_data)
            
            with open(output_path, 'wb') as f:
                f.write(encrypted_data)
            
            return True
        except Exception as e:
            logger.error(f"Error encrypting file: {e}")
            return False
    
    def decrypt_file(self, input_path: str, output_path: str):
        """Decrypt file and save to output path"""
        try:
            with open(input_path, 'rb') as f:
                encrypted_data = f.read()
            
            # Extract IV and ciphertext
            iv = encrypted_data[:AES.block_size]
            ciphertext = encrypted_data[AES.block_size:]
            
            cipher = AES.new(self.key, AES.MODE_CBC, iv)
            decrypted_padded = cipher.decrypt(ciphertext)
            decrypted_data = unpad(decrypted_padded, AES.block_size)
            
            with open(output_path, 'wb') as f:
                f.write(decrypted_data)
            
            return True
        except Exception as e:
            logger.error(f"Error decrypting file: {e}")
            return False

# Rest of the utils functions remain the same...
    
    def encrypt_data(self, data: bytes) -> bytes:
        """Encrypt bytes data"""
        return self.cipher.encrypt(data)
    
    def decrypt_data(self, encrypted_data: bytes) -> bytes:
        """Decrypt bytes data"""
        return self.cipher.decrypt(encrypted_data)

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO,
        handlers=[
            logging.FileHandler('nexa_net_bot.log'),
            logging.StreamHandler()
        ]
    )

def format_bytes(size: int) -> str:
    """Format bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"

def format_date(date_str: str) -> str:
    """Format ISO date string to readable format"""
    if not date_str:
        return "Never"
    try:
        dt = datetime.fromisoformat(date_str)
        return dt.strftime("%d/%m/%Y %H:%M")
    except:
        return date_str

def format_timedelta(delta: timedelta) -> str:
    """Format timedelta to readable format"""
    days = delta.days
    hours = delta.seconds // 3600
    
    if days > 0:
        return f"{days} day{'s' if days != 1 else ''}"
    elif hours > 0:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    else:
        minutes = delta.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''}"

def get_time_until_expiry(expiry_date: str) -> str:
    """Get time remaining until expiry"""
    if not expiry_date:
        return "Expired"
    
    try:
        expiry = datetime.fromisoformat(expiry_date)
        now = datetime.now()
        
        if expiry < now:
            return "Expired"
        
        delta = expiry - now
        return format_timedelta(delta)
    except:
        return "Unknown"

def create_menu_keyboard(buttons_per_row: int = 2) -> InlineKeyboardMarkup:
    """Create standard menu keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("📱 Get Configs", callback_data="category_select"),
            InlineKeyboardButton("💳 Make Payment", callback_data="make_payment")
        ],
        [
            InlineKeyboardButton("📊 My Status", callback_data="my_status"),
            InlineKeyboardButton("❓ Help", callback_data="help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_category_keyboard() -> InlineKeyboardMarkup:
    """Create category selection keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("🟢 Safaricom", callback_data="category_Safaricom"),
            InlineKeyboardButton("🔴 Airtel", callback_data="category_Airtel")
        ],
        [
            InlineKeyboardButton("🟡 Telkom", callback_data="category_Telkom"),
            InlineKeyboardButton("🔵 Other", callback_data="category_Other")
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_admin_keyboard() -> InlineKeyboardMarkup:
    """Create admin panel keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("📊 Statistics", callback_data="admin_stats"),
            InlineKeyboardButton("👥 View Users", callback_data="admin_users")
        ],
        [
            InlineKeyboardButton("💳 Payment Approvals", callback_data="admin_payments"),
            InlineKeyboardButton("📁 Upload Config", callback_data="admin_upload")
        ],
        [
            InlineKeyboardButton("🗑️ Delete Config", callback_data="admin_delete_config"),
            InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton("🔄 Expire User", callback_data="admin_expire_user"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_configs_keyboard(configs: list, page: int = 0, configs_per_page: int = 10) -> Tuple[InlineKeyboardMarkup, int]:
    """Create keyboard for configs list with pagination"""
    start_idx = page * configs_per_page
    end_idx = start_idx + configs_per_page
    
    current_configs = configs[start_idx:end_idx]
    
    keyboard = []
    for config in current_configs:
        filename = config['original_filename']
        if len(filename) > 30:
            filename = filename[:27] + "..."
        button_text = f"📥 {filename}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"download_{config['config_id']}")])
    
    # Navigation buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"configs_page_{page-1}"))
    
    if end_idx < len(configs):
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"configs_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("⬅️ Back to Categories", callback_data="category_select")])
    
    total_pages = (len(configs) + configs_per_page - 1) // configs_per_page
    current_page = page + 1 if current_configs else 0
    
    return InlineKeyboardMarkup(keyboard), current_page

def create_back_button(target: str = "menu") -> InlineKeyboardMarkup:
    """Create simple back button keyboard"""
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data=target)]]
    return InlineKeyboardMarkup(keyboard)

def check_channel_membership(bot, user_id: int) -> bool:
    """Check if user is member of official channel"""
    try:
        chat_member = bot.get_chat_member(chat_id="@nexanetofficial", user_id=user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking channel membership: {e}")
        return False

def get_file_extension(filename: str) -> str:
    """Get file extension in lowercase"""
    return os.path.splitext(filename)[1].lower().replace('.', '')

def is_valid_config_extension(filename: str) -> bool:
    """Check if file has valid config extension"""
    valid_extensions = ['hc', 'ehi', 'ziv', 'dark', 'json']
    ext = get_file_extension(filename)
    return ext in valid_extensions

def generate_filename(original_name: str, user_id: int) -> str:
    """Generate encrypted filename"""
    timestamp = int(datetime.now().timestamp())
    hash_input = f"{original_name}_{user_id}_{timestamp}"
    hash_digest = hashlib.md5(hash_input.encode()).hexdigest()[:8]
    ext = get_file_extension(original_name)
    return f"config_{hash_digest}.{ext}.enc"

def ensure_directories():
    """Ensure required directories exist"""
    directories = ['data', 'configs', 'payments', 'temp']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

def cleanup_temp_files(max_age_hours: int = 24):
    """Clean up old temporary files"""
    try:
        temp_dir = 'temp'
        if not os.path.exists(temp_dir):
            return
        
        now = datetime.now()
        for filename in os.listdir(temp_dir):
            filepath = os.path.join(temp_dir, filename)
            if os.path.isfile(filepath):
                file_age = now - datetime.fromtimestamp(os.path.getctime(filepath))
                if file_age.total_seconds() > max_age_hours * 3600:
                    os.remove(filepath)
                    logger.info(f"Cleaned up temp file: {filename}")
    except Exception as e:
        logger.error(f"Error cleaning temp files: {e}")
