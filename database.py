"""
SQLite database module for NEXA NET VPN Bot
Handles all database operations
"""
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
import json

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "data/nexa_net.db"):
        """Initialize database connection and create tables"""
        self.db_path = db_path
        self.create_tables()
    
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def create_tables(self):
        """Create all necessary tables if they don't exist"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expiry_date TIMESTAMP,
                    payment_status TEXT DEFAULT 'pending',
                    total_downloads INTEGER DEFAULT 0,
                    is_admin INTEGER DEFAULT 0
                )
            ''')
            
            # Configs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS configs (
                    config_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT UNIQUE,
                    category TEXT,
                    original_filename TEXT,
                    file_size INTEGER,
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expiry_date TIMESTAMP,
                    total_downloads INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1
                )
            ''')
            
            # Payments table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    payment_proof TEXT,
                    status TEXT DEFAULT 'pending',
                    admin_note TEXT,
                    processed_date TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Downloads table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS downloads (
                    download_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    config_id INTEGER,
                    download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (config_id) REFERENCES configs (config_id)
                )
            ''')
            
            # Add admin user if not exists
            cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, username, is_admin, payment_status)
                VALUES (7108127485, 'nexanetadmin', 1, 'approved')
            ''')
            
            conn.commit()
    
    # User operations
    def add_user(self, user_id: int, username: str) -> bool:
        """Add new user to database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO users (user_id, username)
                    VALUES (?, ?)
                ''', (user_id, username))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            return False
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None
    
    def update_user_expiry(self, user_id: int, days: int = 30):
        """Update user expiry date (add days)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                current_expiry = self.get_user(user_id)['expiry_date']
                
                if current_expiry:
                    current_date = datetime.fromisoformat(current_expiry)
                    new_expiry = current_date + timedelta(days=days)
                else:
                    new_expiry = datetime.now() + timedelta(days=days)
                
                cursor.execute('''
                    UPDATE users 
                    SET expiry_date = ?, payment_status = 'approved'
                    WHERE user_id = ?
                ''', (new_expiry.isoformat(), user_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating user expiry: {e}")
    
    def update_payment_status(self, user_id: int, status: str):
        """Update user payment status"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users 
                    SET payment_status = ?
                    WHERE user_id = ?
                ''', (status, user_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating payment status: {e}")
    
    def increment_downloads(self, user_id: int):
        """Increment user's total downloads"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users 
                    SET total_downloads = total_downloads + 1
                    WHERE user_id = ?
                ''', (user_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"Error incrementing downloads: {e}")
    
    def delete_expired_users(self):
        """Delete users whose expiry date has passed"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                current_time = datetime.now().isoformat()
                cursor.execute('''
                    DELETE FROM users 
                    WHERE expiry_date < ? 
                    AND payment_status = 'approved'
                    AND user_id != 7108127485
                ''', (current_time,))
                deleted_count = cursor.rowcount
                conn.commit()
                return deleted_count
        except Exception as e:
            logger.error(f"Error deleting expired users: {e}")
            return 0
    
    # Payment operations
    def add_payment(self, user_id: int, amount: float, proof_path: str) -> int:
        """Add new payment record"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO payments (user_id, amount, payment_proof)
                    VALUES (?, ?, ?)
                ''', (user_id, amount, proof_path))
                payment_id = cursor.lastrowid
                conn.commit()
                return payment_id
        except Exception as e:
            logger.error(f"Error adding payment: {e}")
            return -1
    
    def get_pending_payments(self) -> List[Dict]:
        """Get all pending payments"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT p.*, u.username 
                    FROM payments p
                    JOIN users u ON p.user_id = u.user_id
                    WHERE p.status = 'pending'
                    ORDER BY p.payment_date
                ''')
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting pending payments: {e}")
            return []
    
    def update_payment(self, payment_id: int, status: str, admin_note: str = ""):
        """Update payment status"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                processed_date = datetime.now().isoformat() if status != 'pending' else None
                cursor.execute('''
                    UPDATE payments 
                    SET status = ?, admin_note = ?, processed_date = ?
                    WHERE payment_id = ?
                ''', (status, admin_note, processed_date, payment_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating payment: {e}")
    
    # Config operations
    def add_config(self, filename: str, original_filename: str, 
                   category: str, file_size: int, expiry_days: int = 30) -> int:
        """Add new config to database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                expiry_date = (datetime.now() + timedelta(days=expiry_days)).isoformat()
                cursor.execute('''
                    INSERT INTO configs (filename, original_filename, category, 
                                        file_size, expiry_date)
                    VALUES (?, ?, ?, ?, ?)
                ''', (filename, original_filename, category, file_size, expiry_date))
                config_id = cursor.lastrowid
                conn.commit()
                return config_id
        except Exception as e:
            logger.error(f"Error adding config: {e}")
            return -1
    
    def get_configs_by_category(self, category: str) -> List[Dict]:
        """Get configs by category"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM configs 
                    WHERE category = ? AND is_active = 1
                    ORDER BY upload_date DESC
                ''', (category,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting configs: {e}")
            return []
    
    def get_all_configs(self) -> List[Dict]:
        """Get all active configs"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM configs 
                    WHERE is_active = 1
                    ORDER BY upload_date DESC
                ''')
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting all configs: {e}")
            return []
    
    def get_config(self, config_id: int) -> Optional[Dict]:
        """Get config by ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM configs WHERE config_id = ?', (config_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting config: {e}")
            return None
    
    def record_download(self, user_id: int, config_id: int):
        """Record a download and update counters"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Add to downloads table
                cursor.execute('''
                    INSERT INTO downloads (user_id, config_id)
                    VALUES (?, ?)
                ''', (user_id, config_id))
                # Increment config download count
                cursor.execute('''
                    UPDATE configs 
                    SET total_downloads = total_downloads + 1
                    WHERE config_id = ?
                ''', (config_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"Error recording download: {e}")
    
    def delete_expired_configs(self):
        """Delete configs whose expiry date has passed"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                current_time = datetime.now().isoformat()
                cursor.execute('''
                    UPDATE configs 
                    SET is_active = 0
                    WHERE expiry_date < ? AND is_active = 1
                ''', (current_time,))
                expired_count = cursor.rowcount
                conn.commit()
                return expired_count
        except Exception as e:
            logger.error(f"Error deleting expired configs: {e}")
            return 0
    
    def delete_config(self, config_id: int) -> bool:
        """Delete config by ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM configs WHERE config_id = ?', (config_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error deleting config: {e}")
            return False
    
    # Stats operations
    def get_stats(self) -> Dict:
        """Get system statistics"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Total users
                cursor.execute('SELECT COUNT(*) FROM users')
                total_users = cursor.fetchone()[0]
                
                # Active users
                cursor.execute('''
                    SELECT COUNT(*) FROM users 
                    WHERE expiry_date > ? AND payment_status = 'approved'
                ''', (datetime.now().isoformat(),))
                active_users = cursor.fetchone()[0]
                
                # Total configs
                cursor.execute('SELECT COUNT(*) FROM configs WHERE is_active = 1')
                total_configs = cursor.fetchone()[0]
                
                # Total downloads
                cursor.execute('SELECT COUNT(*) FROM downloads')
                total_downloads = cursor.fetchone()[0]
                
                # Today's downloads
                today = datetime.now().date().isoformat()
                cursor.execute('''
                    SELECT COUNT(*) FROM downloads 
                    WHERE DATE(download_date) = ?
                ''', (today,))
                today_downloads = cursor.fetchone()[0]
                
                # Pending payments
                cursor.execute('SELECT COUNT(*) FROM payments WHERE status = "pending"')
                pending_payments = cursor.fetchone()[0]
                
                return {
                    'total_users': total_users,
                    'active_users': active_users,
                    'total_configs': total_configs,
                    'total_downloads': total_downloads,
                    'today_downloads': today_downloads,
                    'pending_payments': pending_payments
                }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}
    
    def get_all_users(self) -> List[Dict]:
        """Get all users"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM users 
                    ORDER BY join_date DESC
                ''')
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting users: {e}")
            return []
