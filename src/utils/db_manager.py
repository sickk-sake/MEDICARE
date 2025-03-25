import os
import sqlite3
import logging
import json
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)

class DatabaseManager:
    """SQLite database manager for medicine reminder application"""
    
    def __init__(self, db_path=None):
        """
        Initialize the database manager
        
        Args:
            db_path: Path to SQLite database file (default: data/medicine_db.sqlite)
        """
        if db_path is None:
            # Use default path relative to project root
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            data_dir = os.path.join(base_dir, 'data')
            
            # Ensure data directory exists
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)
                
            self.db_path = os.path.join(data_dir, 'medicine_db.sqlite')
        else:
            self.db_path = db_path
            
        logger.debug(f"Database path: {self.db_path}")
        
        # Initialize database (create tables if not exist)
        self._initialize_db()
        
    def _initialize_db(self):
        """Create database tables if they don't exist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create medicines table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS medicines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT,
                name TEXT NOT NULL,
                dosage TEXT,
                expiry_date TEXT,
                reminder_frequency TEXT DEFAULT 'daily',
                times_per_day INTEGER DEFAULT 1,
                reminder_time TEXT,
                system_notify BOOLEAN DEFAULT 1,
                telegram_notify BOOLEAN DEFAULT 0,
                calendar_sync BOOLEAN DEFAULT 0,
                calendar_event_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Create reminders table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                medicine_id INTEGER,
                scheduled_time TIMESTAMP NOT NULL,
                taken BOOLEAN DEFAULT 0,
                taken_time TIMESTAMP,
                FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE
            )
            ''')
            
            # Create streak tracking table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS streaks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE,
                completed BOOLEAN DEFAULT 0,
                medicines_total INTEGER DEFAULT 0,
                medicines_taken INTEGER DEFAULT 0
            )
            ''')
            
            # Create settings table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE,
                value TEXT
            )
            ''')
            
            # Create sync logs table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT,
                details TEXT
            )
            ''')
            
            # Create triggers to update timestamps
            cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS update_medicine_timestamp
            AFTER UPDATE ON medicines
            BEGIN
                UPDATE medicines SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;
            ''')
            
            conn.commit()
            logger.debug("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
            
        finally:
            if conn:
                conn.close()
    
    def add_medicine(self, medicine_data):
        """
        Add a new medicine to the database
        
        Args:
            medicine_data: Dictionary containing medicine details
            
        Returns:
            Medicine ID if successful, None otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Insert medicine record
            query = '''
            INSERT INTO medicines (
                barcode, name, dosage, expiry_date, 
                reminder_frequency, times_per_day, reminder_time,
                system_notify, telegram_notify, calendar_sync
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''
            
            cursor.execute(query, (
                medicine_data.get('barcode', ''),
                medicine_data['name'],
                medicine_data.get('dosage', ''),
                medicine_data.get('expiry_date', ''),
                medicine_data.get('reminder_frequency', 'daily'),
                medicine_data.get('times_per_day', 1),
                medicine_data.get('reminder_time', '09:00'),
                medicine_data.get('system_notify', True),
                medicine_data.get('telegram_notify', False),
                medicine_data.get('calendar_sync', False)
            ))
            
            medicine_id = cursor.lastrowid
            
            # Generate reminders based on frequency
            self._generate_reminders(conn, medicine_id, medicine_data)
            
            conn.commit()
            logger.info(f"Added medicine: {medicine_data['name']} (ID: {medicine_id})")
            
            return medicine_id
            
        except Exception as e:
            logger.error(f"Error adding medicine: {e}")
            if conn:
                conn.rollback()
            return None
            
        finally:
            if conn:
                conn.close()
    
    def _generate_reminders(self, conn, medicine_id, medicine_data):
        """
        Generate reminder entries based on medicine schedule
        
        Args:
            conn: Database connection
            medicine_id: Medicine ID
            medicine_data: Medicine data dictionary
        """
        cursor = conn.cursor()
        
        # Get schedule parameters
        frequency = medicine_data.get('reminder_frequency', 'daily')
        times_per_day = medicine_data.get('times_per_day', 1)
        reminder_time = medicine_data.get('reminder_time', '09:00')
        
        # Calculate reminder times
        try:
            base_hour, base_minute = map(int, reminder_time.split(':'))
            today = datetime.now().date()
            
            # Generate reminders for the next 30 days
            for day_offset in range(30):
                target_date = today + timedelta(days=day_offset)
                
                # Skip days based on frequency
                if frequency == 'weekly' and day_offset % 7 != 0:
                    continue
                elif frequency == 'monthly' and target_date.day != today.day:
                    continue
                
                # Generate multiple reminders per day if needed
                for time_idx in range(times_per_day):
                    # Space out multiple daily reminders by 4 hours
                    hour_offset = 4 * time_idx
                    reminder_hour = (base_hour + hour_offset) % 24
                    
                    # Create datetime for the reminder
                    reminder_datetime = datetime.combine(
                        target_date, 
                        datetime.min.time().replace(hour=reminder_hour, minute=base_minute)
                    )
                    
                    # Insert reminder
                    cursor.execute(
                        "INSERT INTO reminders (medicine_id, scheduled_time) VALUES (?, ?)",
                        (medicine_id, reminder_datetime.strftime('%Y-%m-%d %H:%M:%S'))
                    )
            
            logger.debug(f"Generated reminders for medicine ID {medicine_id}")
            
        except Exception as e:
            logger.error(f"Error generating reminders: {e}")
            raise
    
    def update_medicine(self, medicine_data):
        """
        Update an existing medicine in the database
        
        Args:
            medicine_data: Dictionary containing medicine details (must include 'id')
            
        Returns:
            True if successful, False otherwise
        """
        if 'id' not in medicine_data:
            logger.error("Cannot update medicine: ID not provided")
            return False
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Update medicine record
            query = '''
            UPDATE medicines SET
                barcode = ?,
                name = ?,
                dosage = ?,
                expiry_date = ?,
                reminder_frequency = ?,
                times_per_day = ?,
                reminder_time = ?,
                system_notify = ?,
                telegram_notify = ?,
                calendar_sync = ?
            WHERE id = ?
            '''
            
            cursor.execute(query, (
                medicine_data.get('barcode', ''),
                medicine_data['name'],
                medicine_data.get('dosage', ''),
                medicine_data.get('expiry_date', ''),
                medicine_data.get('reminder_frequency', 'daily'),
                medicine_data.get('times_per_day', 1),
                medicine_data.get('reminder_time', '09:00'),
                medicine_data.get('system_notify', True),
                medicine_data.get('telegram_notify', False),
                medicine_data.get('calendar_sync', False),
                medicine_data['id']
            ))
            
            # Delete future reminders
            cursor.execute(
                "DELETE FROM reminders WHERE medicine_id = ? AND scheduled_time > datetime('now')",
                (medicine_data['id'],)
            )
            
            # Regenerate reminders
            self._generate_reminders(conn, medicine_data['id'], medicine_data)
            
            conn.commit()
            logger.info(f"Updated medicine: {medicine_data['name']} (ID: {medicine_data['id']})")
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating medicine: {e}")
            if conn:
                conn.rollback()
            return False
            
        finally:
            if conn:
                conn.close()
    
    def delete_medicine(self, medicine_id):
        """
        Delete a medicine and its reminders from the database
        
        Args:
            medicine_id: Medicine ID to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get medicine name for logging
            cursor.execute("SELECT name FROM medicines WHERE id = ?", (medicine_id,))
            result = cursor.fetchone()
            medicine_name = result[0] if result else "Unknown"
            
            # Delete the medicine (reminders will cascade)
            cursor.execute("DELETE FROM medicines WHERE id = ?", (medicine_id,))
            
            conn.commit()
            logger.info(f"Deleted medicine: {medicine_name} (ID: {medicine_id})")
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting medicine: {e}")
            if conn:
                conn.rollback()
            return False
            
        finally:
            if conn:
                conn.close()
    
    def get_all_medicines(self):
        """
        Get all medicines from the database
        
        Returns:
            List of medicine dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT m.*, 
                   (SELECT MIN(scheduled_time) 
                    FROM reminders 
                    WHERE medicine_id = m.id AND taken = 0 AND scheduled_time > datetime('now')
                   ) as next_reminder
            FROM medicines m
            ORDER BY name
            ''')
            
            medicines = []
            for row in cursor.fetchall():
                medicine = dict(row)
                medicines.append(medicine)
            
            return medicines
            
        except Exception as e:
            logger.error(f"Error getting all medicines: {e}")
            return []
            
        finally:
            if conn:
                conn.close()
    
    def get_medicine_by_id(self, medicine_id):
        """
        Get a medicine by its ID
        
        Args:
            medicine_id: Medicine ID
            
        Returns:
            Medicine dictionary if found, None otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT m.*, 
                   (SELECT MIN(scheduled_time) 
                    FROM reminders 
                    WHERE medicine_id = m.id AND taken = 0 AND scheduled_time > datetime('now')
                   ) as next_reminder
            FROM medicines m
            WHERE m.id = ?
            ''', (medicine_id,))
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting medicine by ID {medicine_id}: {e}")
            return None
            
        finally:
            if conn:
                conn.close()
    
    def get_medicine_by_barcode(self, barcode):
        """
        Get a medicine by its barcode
        
        Args:
            barcode: Medicine barcode
            
        Returns:
            Medicine dictionary if found, None otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT m.*, 
                   (SELECT MIN(scheduled_time) 
                    FROM reminders 
                    WHERE medicine_id = m.id AND taken = 0 AND scheduled_time > datetime('now')
                   ) as next_reminder
            FROM medicines m
            WHERE m.barcode = ?
            ''', (barcode,))
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting medicine by barcode {barcode}: {e}")
            return None
            
        finally:
            if conn:
                conn.close()
    
    def get_upcoming_reminders(self, start_time, end_time):
        """
        Get upcoming medicine reminders for a time period
        
        Args:
            start_time: Start datetime
            end_time: End datetime
            
        Returns:
            List of reminder dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT r.id as reminder_id, r.scheduled_time, m.id, m.name, m.dosage, 
                   m.system_notify, m.telegram_notify, m.calendar_sync
            FROM reminders r
            JOIN medicines m ON r.medicine_id = m.id
            WHERE r.taken = 0 
              AND r.scheduled_time BETWEEN ? AND ?
            ORDER BY r.scheduled_time
            ''', (
                start_time.strftime('%Y-%m-%d %H:%M:%S'), 
                end_time.strftime('%Y-%m-%d %H:%M:%S')
            ))
            
            reminders = []
            for row in cursor.fetchall():
                reminder = dict(row)
                # Set the next_reminder field for consistency
                reminder['next_reminder'] = reminder['scheduled_time']
                reminders.append(reminder)
            
            return reminders
            
        except Exception as e:
            logger.error(f"Error getting upcoming reminders: {e}")
            return []
            
        finally:
            if conn:
                conn.close()
    
    def get_todays_reminders(self):
        """
        Get today's medicine reminders
        
        Returns:
            List of reminder dictionaries
        """
        today = datetime.now().date()
        start_time = datetime.combine(today, datetime.min.time())
        end_time = datetime.combine(today, datetime.max.time())
        
        return self.get_upcoming_reminders(start_time, end_time)
    
    def mark_medicine_taken(self, medicine_id):
        """
        Mark a medicine as taken
        
        Args:
            medicine_id: Medicine ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get the earliest untaken reminder for this medicine
            cursor.execute('''
            SELECT id, scheduled_time 
            FROM reminders 
            WHERE medicine_id = ? AND taken = 0
            ORDER BY scheduled_time
            LIMIT 1
            ''', (medicine_id,))
            
            row = cursor.fetchone()
            if not row:
                logger.warning(f"No pending reminders found for medicine ID {medicine_id}")
                return False
                
            reminder_id, scheduled_time = row
            
            # Mark reminder as taken
            now = datetime.now()
            cursor.execute('''
            UPDATE reminders 
            SET taken = 1, taken_time = ? 
            WHERE id = ?
            ''', (now.strftime('%Y-%m-%d %H:%M:%S'), reminder_id))
            
            # Update streak for today
            today = now.date().strftime('%Y-%m-%d')
            
            # Check if we already have a streak record for today
            cursor.execute("SELECT id FROM streaks WHERE date = ?", (today,))
            streak_row = cursor.fetchone()
            
            if streak_row:
                # Update existing streak
                cursor.execute('''
                UPDATE streaks 
                SET medicines_taken = medicines_taken + 1 
                WHERE date = ?
                ''', (today,))
                
                # Check if all medicines for today are taken
                cursor.execute('''
                SELECT COUNT(*) as total, 
                       SUM(CASE WHEN taken = 1 THEN 1 ELSE 0 END) as taken
                FROM reminders
                WHERE date(scheduled_time) = date(?)
                ''', (today,))
                
                counts = cursor.fetchone()
                if counts and counts[0] == counts[1]:  # All taken
                    cursor.execute('''
                    UPDATE streaks SET completed = 1 WHERE date = ?
                    ''', (today,))
            else:
                # Create new streak record
                cursor.execute('''
                INSERT INTO streaks (date, medicines_taken, medicines_total)
                VALUES (?, 1, (SELECT COUNT(*) FROM reminders WHERE date(scheduled_time) = date(?)))
                ''', (today, today))
            
            conn.commit()
            logger.info(f"Marked medicine ID {medicine_id} as taken")
            
            return True
            
        except Exception as e:
            logger.error(f"Error marking medicine as taken: {e}")
            if conn:
                conn.rollback()
            return False
            
        finally:
            if conn:
                conn.close()
    
    def update_reminder_status(self, reminder_id):
        """
        Update a reminder's status
        
        Args:
            reminder_id: Reminder ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            now = datetime.now()
            cursor.execute('''
            UPDATE reminders 
            SET taken = 1, taken_time = ? 
            WHERE id = ?
            ''', (now.strftime('%Y-%m-%d %H:%M:%S'), reminder_id))
            
            conn.commit()
            logger.debug(f"Updated reminder status for ID {reminder_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating reminder status: {e}")
            if conn:
                conn.rollback()
            return False
            
        finally:
            if conn:
                conn.close()
    
    def get_current_streak(self):
        """
        Get the current streak (consecutive days with all medicines taken)
        
        Returns:
            Streak count (integer)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get dates in reverse order to count consecutive completed days
            cursor.execute('''
            SELECT date, completed 
            FROM streaks 
            ORDER BY date DESC
            ''')
            
            rows = cursor.fetchall()
            
            streak = 0
            today = datetime.now().date()
            
            for i, (date_str, completed) in enumerate(rows):
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                
                # For first row (today/most recent), if not completed but have taken some,
                # still count as in progress for streak
                if i == 0 and not completed:
                    # Check if any medicines taken today
                    cursor.execute('''
                    SELECT COUNT(*) FROM reminders 
                    WHERE date(scheduled_time) = date(?) AND taken = 1
                    ''', (date_str,))
                    
                    taken_count = cursor.fetchone()[0]
                    if taken_count > 0:
                        streak += 1
                        continue
                    else:
                        break
                        
                # If this date is completed and consecutive with previous date
                if completed:
                    # For days other than first day, ensure they're consecutive
                    if i > 0:
                        prev_date = datetime.strptime(rows[i-1][0], '%Y-%m-%d').date()
                        if (prev_date - date).days != 1:
                            break
                    streak += 1
                else:
                    break
            
            return streak
            
        except Exception as e:
            logger.error(f"Error getting current streak: {e}")
            return 0
            
        finally:
            if conn:
                conn.close()
    
    def get_adherence_rate(self):
        """
        Calculate the medication adherence rate (percentage of taken vs. scheduled)
        
        Returns:
            Adherence rate as percentage (float)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get the statistics for the last 30 days
            thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            cursor.execute('''
            SELECT COUNT(*) as total, 
                   SUM(CASE WHEN taken = 1 THEN 1 ELSE 0 END) as taken
            FROM reminders
            WHERE scheduled_time <= datetime('now') 
              AND scheduled_time >= datetime(?)
            ''', (thirty_days_ago,))
            
            row = cursor.fetchone()
            if not row or row[0] == 0:
                return 0.0
                
            total, taken = row
            adherence_rate = (taken / total) * 100
            
            return adherence_rate
            
        except Exception as e:
            logger.error(f"Error calculating adherence rate: {e}")
            return 0.0
            
        finally:
            if conn:
                conn.close()
    
    def get_month_schedule(self, year, month):
        """
        Get the medication schedule for a specific month
        
        Args:
            year: Year (integer)
            month: Month (integer, 1-12)
            
        Returns:
            Dictionary mapping date strings to lists of medicines
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Format month and year for query
            start_date = f"{year}-{month:02d}-01"
            # Calculate end date (first day of next month)
            if month == 12:
                end_date = f"{year+1}-01-01"
            else:
                end_date = f"{year}-{month+1:02d}-01"
            
            cursor.execute('''
            SELECT r.id as reminder_id, r.scheduled_time, r.taken,
                   m.id, m.name, m.dosage, m.reminder_time
            FROM reminders r
            JOIN medicines m ON r.medicine_id = m.id
            WHERE r.scheduled_time >= ? AND r.scheduled_time < ?
            ORDER BY r.scheduled_time
            ''', (start_date, end_date))
            
            # Organize reminders by date
            schedule = {}
            for row in cursor.fetchall():
                reminder = dict(row)
                
                # Extract date string (YYYY-MM-DD) from scheduled_time
                date_str = reminder['scheduled_time'].split(' ')[0]
                
                if date_str not in schedule:
                    schedule[date_str] = []
                    
                schedule[date_str].append(reminder)
            
            return schedule
            
        except Exception as e:
            logger.error(f"Error getting month schedule: {e}")
            return {}
            
        finally:
            if conn:
                conn.close()
    
    def get_day_schedule(self, date_str):
        """
        Get the medication schedule for a specific day
        
        Args:
            date_str: Date string in format 'YYYY-MM-DD'
            
        Returns:
            List of medicine dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT r.id as reminder_id, r.scheduled_time, r.taken,
                   m.id, m.name, m.dosage, 
                   time(r.scheduled_time) as reminder_time
            FROM reminders r
            JOIN medicines m ON r.medicine_id = m.id
            WHERE date(r.scheduled_time) = date(?)
            ORDER BY r.scheduled_time
            ''', (date_str,))
            
            reminders = []
            for row in cursor.fetchall():
                reminder = dict(row)
                reminders.append(reminder)
            
            return reminders
            
        except Exception as e:
            logger.error(f"Error getting day schedule: {e}")
            return []
            
        finally:
            if conn:
                conn.close()
    
    def get_expiring_medicines(self, days=30):
        """
        Get medicines that are expiring soon or have already expired
        
        Args:
            days: Number of days to look ahead (default: 30)
            
        Returns:
            List of expiring medicine dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Calculate cutoff date
            cutoff_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
            
            cursor.execute('''
            SELECT * FROM medicines
            WHERE expiry_date <= ? AND expiry_date >= date('now')
            ORDER BY expiry_date
            ''', (cutoff_date,))
            
            medicines = []
            for row in cursor.fetchall():
                medicine = dict(row)
                medicines.append(medicine)
            
            # Also get already expired medicines
            cursor.execute('''
            SELECT * FROM medicines
            WHERE expiry_date < date('now')
            ORDER BY expiry_date DESC
            ''')
            
            for row in cursor.fetchall():
                medicine = dict(row)
                medicines.append(medicine)
            
            return medicines
            
        except Exception as e:
            logger.error(f"Error getting expiring medicines: {e}")
            return []
            
        finally:
            if conn:
                conn.close()
    
    def save_user_settings(self, settings):
        """
        Save user settings to the database
        
        Args:
            settings: Dictionary of settings
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Save each setting
            for key, value in settings.items():
                # Convert boolean and numeric values to strings
                if isinstance(value, bool):
                    value = '1' if value else '0'
                elif isinstance(value, (int, float)):
                    value = str(value)
                
                # Check if key exists
                cursor.execute("SELECT id FROM settings WHERE key = ?", (key,))
                if cursor.fetchone():
                    # Update existing setting
                    cursor.execute("UPDATE settings SET value = ? WHERE key = ?", (value, key))
                else:
                    # Insert new setting
                    cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, value))
            
            conn.commit()
            logger.debug("User settings saved successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving user settings: {e}")
            if conn:
                conn.rollback()
            return False
            
        finally:
            if conn:
                conn.close()
    
    def get_user_settings(self):
        """
        Get user settings from the database
        
        Returns:
            Dictionary of settings
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT key, value FROM settings")
            
            settings = {}
            for key, value in cursor.fetchall():
                # Convert numeric and boolean values
                if value.isdigit():
                    settings[key] = int(value)
                elif value.lower() in ('true', 'false', '1', '0'):
                    settings[key] = value.lower() in ('true', '1')
                else:
                    settings[key] = value
            
            return settings
            
        except Exception as e:
            logger.error(f"Error getting user settings: {e}")
            return {}
            
        finally:
            if conn:
                conn.close()
    
    def update_telegram_settings(self, chat_id):
        """
        Update Telegram settings
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if key exists
            cursor.execute("SELECT id FROM settings WHERE key = 'telegram_chat_id'")
            if cursor.fetchone():
                # Update existing setting
                cursor.execute("UPDATE settings SET value = ? WHERE key = 'telegram_chat_id'", (chat_id,))
            else:
                # Insert new setting
                cursor.execute("INSERT INTO settings (key, value) VALUES ('telegram_chat_id', ?)", (chat_id,))
            
            conn.commit()
            logger.debug(f"Telegram chat ID updated to {chat_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating Telegram settings: {e}")
            if conn:
                conn.rollback()
            return False
            
        finally:
            if conn:
                conn.close()
    
    def log_sync_operation(self, operation, status, details=None):
        """
        Log a sync operation to the database
        
        Args:
            operation: Operation name (e.g., 'backup', 'restore')
            status: Operation status (e.g., 'success', 'error')
            details: Optional details (string or JSON serializable object)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Convert details to JSON if it's not a string
            if details is not None and not isinstance(details, str):
                details = json.dumps(details)
            
            cursor.execute('''
            INSERT INTO sync_logs (operation, status, details)
            VALUES (?, ?, ?)
            ''', (operation, status, details))
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error logging sync operation: {e}")
            if conn:
                conn.rollback()
            return False
            
        finally:
            if conn:
                conn.close()
    
    def get_last_sync_time(self):
        """
        Get the timestamp of the last successful sync
        
        Returns:
            Timestamp string if found, None otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT timestamp FROM sync_logs
            WHERE status = 'success'
            ORDER BY timestamp DESC
            LIMIT 1
            ''')
            
            row = cursor.fetchone()
            return row[0] if row else None
            
        except Exception as e:
            logger.error(f"Error getting last sync time: {e}")
            return None
            
        finally:
            if conn:
                conn.close()
    
    def export_database(self):
        """
        Export database contents as a dictionary for backup purposes
        
        Returns:
            Dictionary containing all database tables and records
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            export_data = {
                'medicines': [],
                'reminders': [],
                'streaks': [],
                'settings': [],
                'export_time': datetime.now().isoformat()
            }
            
            # Export medicines
            cursor.execute("SELECT * FROM medicines")
            for row in cursor.fetchall():
                export_data['medicines'].append(dict(row))
            
            # Export reminders
            cursor.execute("SELECT * FROM reminders")
            for row in cursor.fetchall():
                export_data['reminders'].append(dict(row))
            
            # Export streaks
            cursor.execute("SELECT * FROM streaks")
            for row in cursor.fetchall():
                export_data['streaks'].append(dict(row))
            
            # Export settings
            cursor.execute("SELECT * FROM settings")
            for row in cursor.fetchall():
                export_data['settings'].append(dict(row))
            
            return export_data
            
        except Exception as e:
            logger.error(f"Error exporting database: {e}")
            return None
            
        finally:
            if conn:
                conn.close()
    
    def import_database(self, import_data):
        """
        Import database contents from a backup
        
        Args:
            import_data: Dictionary containing database tables and records
            
        Returns:
            True if successful, False otherwise
        """
        if not import_data or not isinstance(import_data, dict):
            logger.error("Invalid import data")
            return False
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Begin transaction
            conn.execute("BEGIN TRANSACTION")
            
            # Clear existing tables
            cursor.execute("DELETE FROM reminders")
            cursor.execute("DELETE FROM medicines")
            cursor.execute("DELETE FROM streaks")
            cursor.execute("DELETE FROM settings")
            
            # Import medicines
            for medicine in import_data.get('medicines', []):
                columns = ', '.join(medicine.keys())
                placeholders = ', '.join(['?'] * len(medicine))
                query = f"INSERT INTO medicines ({columns}) VALUES ({placeholders})"
                cursor.execute(query, list(medicine.values()))
            
            # Import reminders
            for reminder in import_data.get('reminders', []):
                columns = ', '.join(reminder.keys())
                placeholders = ', '.join(['?'] * len(reminder))
                query = f"INSERT INTO reminders ({columns}) VALUES ({placeholders})"
                cursor.execute(query, list(reminder.values()))
            
            # Import streaks
            for streak in import_data.get('streaks', []):
                columns = ', '.join(streak.keys())
                placeholders = ', '.join(['?'] * len(streak))
                query = f"INSERT INTO streaks ({columns}) VALUES ({placeholders})"
                cursor.execute(query, list(streak.values()))
            
            # Import settings
            for setting in import_data.get('settings', []):
                columns = ', '.join(setting.keys())
                placeholders = ', '.join(['?'] * len(setting))
                query = f"INSERT INTO settings ({columns}) VALUES ({placeholders})"
                cursor.execute(query, list(setting.values()))
            
            # Log the import
            self.log_sync_operation(
                'import', 
                'success', 
                f"Imported from backup created at {import_data.get('export_time', 'unknown')}"
            )
            
            conn.commit()
            logger.info("Database import completed successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"Error importing database: {e}")
            if conn:
                conn.rollback()
            return False
            
        finally:
            if conn:
                conn.close()
