import os
import sqlite3
import logging
import json
import datetime
import psycopg2
from pathlib import Path
from urllib.parse import urlparse

class DatabaseManager:
    """
    A class to handle database operations for the Medicine Reminder App.
    Supports both SQLite and PostgreSQL.
    """
    
    def __init__(self, db_path=None, db_url=None):
        """
        Initialize the database manager with either SQLite or PostgreSQL.
        
        Args:
            db_path (str, optional): Path to the SQLite database file
            db_url (str, optional): PostgreSQL connection URL
        """
        self.logger = logging.getLogger(__name__)
        
        self.db_path = db_path
        self.db_url = db_url
        self.connection = None
        self.cursor = None
        self.is_postgres = db_url is not None
        self.db_type = 'postgresql' if self.is_postgres else 'sqlite'
        
        if self.db_path and not self.is_postgres:
            # Ensure the data directory exists for SQLite
            data_dir = os.path.dirname(db_path)
            if data_dir and not os.path.exists(data_dir):
                os.makedirs(data_dir)
        
        self._connect()
        self._create_tables()
        
    def _connect(self):
        """
        Establish a connection to the database (SQLite or PostgreSQL).
        """
        try:
            if self.is_postgres:
                # PostgreSQL connection
                self.connection = psycopg2.connect(self.db_url)
                self.cursor = self.connection.cursor()
                self.logger.info("Connected to PostgreSQL database")
            else:
                # SQLite connection
                self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
                # Enable foreign key constraints
                self.connection.execute("PRAGMA foreign_keys = ON")
                # Row factory to get dictionary-like results
                self.connection.row_factory = sqlite3.Row
                self.cursor = self.connection.cursor()
                self.logger.info("Connected to SQLite database")
        except Exception as e:
            self.logger.error(f"Database connection error: {str(e)}")
            raise
            
    def _create_tables(self):
        """
        Create the necessary tables in the database if they don't exist.
        """
        try:
            if self.is_postgres:
                # PostgreSQL tables
                
                # Create medicine table
                self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS medicines (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    barcode TEXT,
                    dosage TEXT,
                    notes TEXT,
                    expiry_date TEXT,
                    doses_remaining INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                # Create schedule table
                self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS schedule (
                    id SERIAL PRIMARY KEY,
                    medicine_id INTEGER,
                    day_of_week INTEGER,  -- 0=Monday, 6=Sunday, -1=Every day
                    time TEXT NOT NULL,   -- Format: HH:MM
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE
                )
                ''')
                
                # Create logs table for medicine intake
                self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS intake_logs (
                    id SERIAL PRIMARY KEY,
                    medicine_id INTEGER,
                    intake_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    taken BOOLEAN DEFAULT TRUE,
                    notes TEXT,
                    FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE
                )
                ''')
                
                # Create streak table
                self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS streaks (
                    id SERIAL PRIMARY KEY,
                    current_streak INTEGER DEFAULT 0,
                    longest_streak INTEGER DEFAULT 0,
                    last_taken_date TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                # Create user settings table
                self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    id SERIAL PRIMARY KEY,
                    key TEXT UNIQUE,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                # Check if there's a streak record
                self.cursor.execute("SELECT COUNT(*) FROM streaks")
                count = self.cursor.fetchone()[0]
                
                # Insert default streak record if it doesn't exist
                if count == 0:
                    self.cursor.execute('''
                    INSERT INTO streaks (id, current_streak, longest_streak) 
                    VALUES (1, 0, 0)
                    ''')
                
            else:
                # SQLite tables
                
                # Create medicine table
                self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS medicines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    barcode TEXT,
                    dosage TEXT,
                    notes TEXT,
                    expiry_date TEXT,
                    doses_remaining INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                # Create schedule table
                self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    medicine_id INTEGER,
                    day_of_week INTEGER,  -- 0=Monday, 6=Sunday, -1=Every day
                    time TEXT NOT NULL,   -- Format: HH:MM
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE
                )
                ''')
                
                # Create logs table for medicine intake
                self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS intake_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    medicine_id INTEGER,
                    intake_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    taken BOOLEAN DEFAULT 1,
                    notes TEXT,
                    FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE
                )
                ''')
                
                # Create streak table
                self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS streaks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    current_streak INTEGER DEFAULT 0,
                    longest_streak INTEGER DEFAULT 0,
                    last_taken_date TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                # Create user settings table
                self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                # Insert default streak record if it doesn't exist
                self.cursor.execute('''
                INSERT OR IGNORE INTO streaks (id, current_streak, longest_streak) 
                VALUES (1, 0, 0)
                ''')
            
            self.connection.commit()
            self.logger.info("Database tables created successfully")
            
        except Exception as e:
            self.logger.error(f"Error creating database tables: {str(e)}")
            self.connection.rollback()
            raise
            
    def close(self):
        """
        Close the database connection.
        """
        if self.connection:
            self.connection.close()
            self.connection = None
            self.cursor = None
            self.logger.info("Database connection closed")
            
    def add_medicine(self, name, barcode=None, dosage=None, notes=None, expiry_date=None, doses_remaining=None):
        """
        Add a new medicine to the database.
        
        Args:
            name (str): Medicine name
            barcode (str, optional): Barcode number
            dosage (str, optional): Dosage information
            notes (str, optional): Additional notes
            expiry_date (str, optional): Expiry date in YYYY-MM-DD format
            doses_remaining (int, optional): Number of doses remaining
            
        Returns:
            int: ID of the new medicine or None if error
        """
        try:
            self.cursor.execute('''
            INSERT INTO medicines (name, barcode, dosage, notes, expiry_date, doses_remaining)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, barcode, dosage, notes, expiry_date, doses_remaining))
            
            self.connection.commit()
            medicine_id = self.cursor.lastrowid
            self.logger.info(f"Added medicine: {name} (ID: {medicine_id})")
            return medicine_id
            
        except sqlite3.Error as e:
            self.logger.error(f"Error adding medicine: {str(e)}")
            self.connection.rollback()
            return None
            
    def update_medicine(self, medicine_id, **kwargs):
        """
        Update an existing medicine in the database.
        
        Args:
            medicine_id (int): ID of the medicine to update
            **kwargs: Fields to update (name, barcode, dosage, notes, expiry_date, doses_remaining)
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            # Build the update query dynamically based on provided fields
            valid_fields = ['name', 'barcode', 'dosage', 'notes', 'expiry_date', 'doses_remaining']
            update_fields = []
            values = []
            
            for field, value in kwargs.items():
                if field in valid_fields:
                    update_fields.append(f"{field} = ?")
                    values.append(value)
            
            if not update_fields:
                self.logger.warning("No valid fields provided for medicine update")
                return False
                
            # Add updated_at field
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            
            # Build and execute the query
            query = f"UPDATE medicines SET {', '.join(update_fields)} WHERE id = ?"
            values.append(medicine_id)
            
            self.cursor.execute(query, values)
            self.connection.commit()
            
            if self.cursor.rowcount > 0:
                self.logger.info(f"Updated medicine ID {medicine_id}")
                return True
            else:
                self.logger.warning(f"Medicine ID {medicine_id} not found")
                return False
                
        except sqlite3.Error as e:
            self.logger.error(f"Error updating medicine: {str(e)}")
            self.connection.rollback()
            return False
            
    def delete_medicine(self, medicine_id):
        """
        Delete a medicine from the database.
        
        Args:
            medicine_id (int): ID of the medicine to delete
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            self.cursor.execute("DELETE FROM medicines WHERE id = ?", (medicine_id,))
            self.connection.commit()
            
            if self.cursor.rowcount > 0:
                self.logger.info(f"Deleted medicine ID {medicine_id}")
                return True
            else:
                self.logger.warning(f"Medicine ID {medicine_id} not found")
                return False
                
        except sqlite3.Error as e:
            self.logger.error(f"Error deleting medicine: {str(e)}")
            self.connection.rollback()
            return False
            
    def get_medicine_by_id(self, medicine_id):
        """
        Get a medicine by its ID.
        
        Args:
            medicine_id (int): ID of the medicine
            
        Returns:
            dict: Medicine data or None if not found
        """
        try:
            self.cursor.execute("SELECT * FROM medicines WHERE id = ?", (medicine_id,))
            row = self.cursor.fetchone()
            
            if row:
                return dict(row)
            else:
                return None
                
        except sqlite3.Error as e:
            self.logger.error(f"Error getting medicine by ID: {str(e)}")
            return None
            
    def get_medicine_by_barcode(self, barcode):
        """
        Get a medicine by its barcode.
        
        Args:
            barcode (str): Barcode of the medicine
            
        Returns:
            dict: Medicine data or None if not found
        """
        try:
            self.cursor.execute("SELECT * FROM medicines WHERE barcode = ?", (barcode,))
            row = self.cursor.fetchone()
            
            if row:
                return dict(row)
            else:
                return None
                
        except sqlite3.Error as e:
            self.logger.error(f"Error getting medicine by barcode: {str(e)}")
            return None
            
    def get_all_medicines(self):
        """
        Get all medicines from the database.
        
        Returns:
            list: List of medicine dictionaries
        """
        try:
            self.cursor.execute("SELECT * FROM medicines ORDER BY name")
            rows = self.cursor.fetchall()
            return [dict(row) for row in rows]
            
        except sqlite3.Error as e:
            self.logger.error(f"Error getting all medicines: {str(e)}")
            return []
            
    def add_schedule(self, medicine_id, time, day_of_week=-1):
        """
        Add a schedule for a medicine.
        
        Args:
            medicine_id (int): ID of the medicine
            time (str): Time in HH:MM format
            day_of_week (int, optional): Day of the week (0=Monday, 6=Sunday, -1=Every day)
            
        Returns:
            int: ID of the new schedule or None if error
        """
        try:
            self.cursor.execute('''
            INSERT INTO schedule (medicine_id, time, day_of_week)
            VALUES (?, ?, ?)
            ''', (medicine_id, time, day_of_week))
            
            self.connection.commit()
            schedule_id = self.cursor.lastrowid
            self.logger.info(f"Added schedule for medicine ID {medicine_id} at {time}")
            return schedule_id
            
        except sqlite3.Error as e:
            self.logger.error(f"Error adding schedule: {str(e)}")
            self.connection.rollback()
            return None
            
    def update_schedule(self, schedule_id, time=None, day_of_week=None):
        """
        Update an existing schedule.
        
        Args:
            schedule_id (int): ID of the schedule to update
            time (str, optional): New time in HH:MM format
            day_of_week (int, optional): New day of the week
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            update_fields = []
            values = []
            
            if time is not None:
                update_fields.append("time = ?")
                values.append(time)
                
            if day_of_week is not None:
                update_fields.append("day_of_week = ?")
                values.append(day_of_week)
                
            if not update_fields:
                return False
                
            query = f"UPDATE schedule SET {', '.join(update_fields)} WHERE id = ?"
            values.append(schedule_id)
            
            self.cursor.execute(query, values)
            self.connection.commit()
            
            if self.cursor.rowcount > 0:
                self.logger.info(f"Updated schedule ID {schedule_id}")
                return True
            else:
                self.logger.warning(f"Schedule ID {schedule_id} not found")
                return False
                
        except sqlite3.Error as e:
            self.logger.error(f"Error updating schedule: {str(e)}")
            self.connection.rollback()
            return False
            
    def delete_schedule(self, schedule_id):
        """
        Delete a schedule.
        
        Args:
            schedule_id (int): ID of the schedule to delete
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            self.cursor.execute("DELETE FROM schedule WHERE id = ?", (schedule_id,))
            self.connection.commit()
            
            if self.cursor.rowcount > 0:
                self.logger.info(f"Deleted schedule ID {schedule_id}")
                return True
            else:
                self.logger.warning(f"Schedule ID {schedule_id} not found")
                return False
                
        except sqlite3.Error as e:
            self.logger.error(f"Error deleting schedule: {str(e)}")
            self.connection.rollback()
            return False
            
    def get_schedules_for_medicine(self, medicine_id):
        """
        Get all schedules for a specific medicine.
        
        Args:
            medicine_id (int): ID of the medicine
            
        Returns:
            list: List of schedule dictionaries
        """
        try:
            self.cursor.execute('''
            SELECT s.*, m.name as medicine_name, m.dosage
            FROM schedule s
            JOIN medicines m ON s.medicine_id = m.id
            WHERE s.medicine_id = ?
            ORDER BY s.day_of_week, s.time
            ''', (medicine_id,))
            
            rows = self.cursor.fetchall()
            return [dict(row) for row in rows]
            
        except sqlite3.Error as e:
            self.logger.error(f"Error getting schedules for medicine: {str(e)}")
            return []
            
    def get_medicines_for_time(self, time):
        """
        Get medicines scheduled for a specific time.
        
        Args:
            time (str): Time in HH:MM format
            
        Returns:
            list: List of medicine dictionaries
        """
        try:
            today = datetime.datetime.now().weekday()  # 0=Monday, 6=Sunday
            
            if self.db_type == 'sqlite':
                self.cursor.execute('''
                SELECT m.*, s.time
                FROM medicines m
                JOIN schedule s ON m.id = s.medicine_id
                WHERE s.time = ? AND (s.day_of_week = -1 OR s.day_of_week = ?)
                ''', (time, today))
            else:  # PostgreSQL
                self.cursor.execute('''
                SELECT m.*, s.time
                FROM medicines m
                JOIN schedule s ON m.id = s.medicine_id
                WHERE s.time = %s AND (s.day_of_week = -1 OR s.day_of_week = %s)
                ''', (time, today))
            
            rows = self.cursor.fetchall()
            
            # Convert to dictionaries based on database type
            if self.db_type == 'sqlite':
                return [dict(row) for row in rows]
            else:  # PostgreSQL
                columns = [desc[0] for desc in self.cursor.description]
                return [dict(zip(columns, row)) for row in rows]
            
        except (sqlite3.Error, psycopg2.Error) as e:
            self.logger.error(f"Error getting medicines for time: {str(e)}")
            return []
            
    def get_medicines_for_date(self, date):
        """
        Get medicines scheduled for a specific date.
        
        Args:
            date (str): Date in YYYY-MM-DD format
            
        Returns:
            list: List of medicine dictionaries with schedule times
        """
        try:
            # Convert date string to datetime to get day of week
            date_obj = datetime.datetime.strptime(date, "%Y-%m-%d")
            day_of_week = date_obj.weekday()  # 0=Monday, 6=Sunday
            
            if self.db_type == 'sqlite':
                self.cursor.execute('''
                SELECT m.id, m.name, m.dosage, s.time
                FROM medicines m
                JOIN schedule s ON m.id = s.medicine_id
                WHERE s.day_of_week = -1 OR s.day_of_week = ?
                ORDER BY s.time
                ''', (day_of_week,))
            else:  # PostgreSQL
                self.cursor.execute('''
                SELECT m.id, m.name, m.dosage, s.time
                FROM medicines m
                JOIN schedule s ON m.id = s.medicine_id
                WHERE s.day_of_week = -1 OR s.day_of_week = %s
                ORDER BY s.time
                ''', (day_of_week,))
            
            rows = self.cursor.fetchall()
            
            # Convert to dictionaries
            if self.db_type == 'sqlite':
                return [dict(row) for row in rows]
            else:  # PostgreSQL
                result = []
                for row in rows:
                    result.append({
                        'id': row[0],
                        'name': row[1],
                        'dosage': row[2],
                        'time': row[3]
                    })
                return result
                
        except (sqlite3.Error, psycopg2.Error) as e:
            self.logger.error(f"Error getting medicines for date: {str(e)}")
            return []
            
    def get_expiring_medicines(self, days=30):
        """
        Get medicines that will expire within the specified number of days.
        
        Args:
            days (int): Number of days to check for expiry
            
        Returns:
            list: List of expiring medicine dictionaries
        """
        try:
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            future_date = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
            
            if self.db_type == 'sqlite':
                self.cursor.execute('''
                SELECT * FROM medicines
                WHERE expiry_date IS NOT NULL 
                AND expiry_date BETWEEN ? AND ?
                ORDER BY expiry_date
                ''', (today, future_date))
            else:  # PostgreSQL
                self.cursor.execute('''
                SELECT * FROM medicines
                WHERE expiry_date IS NOT NULL 
                AND expiry_date BETWEEN %s AND %s
                ORDER BY expiry_date
                ''', (today, future_date))
            
            rows = self.cursor.fetchall()
            
            # Convert to dictionaries based on database type
            if self.db_type == 'sqlite':
                return [dict(row) for row in rows]
            else:  # PostgreSQL
                columns = [desc[0] for desc in self.cursor.description]
                return [dict(zip(columns, row)) for row in rows]
                
        except (sqlite3.Error, psycopg2.Error) as e:
            self.logger.error(f"Error getting expiring medicines: {str(e)}")
            return []
            
    def log_medicine_intake(self, medicine_id, taken=True, notes=None):
        """
        Log the intake of a medicine.
        
        Args:
            medicine_id (int): ID of the medicine
            taken (bool): Whether the medicine was taken
            notes (str, optional): Additional notes
            
        Returns:
            int: ID of the log entry or None if error
        """
        try:
            if self.db_type == 'sqlite':
                self.cursor.execute('''
                INSERT INTO intake_logs (medicine_id, taken, notes)
                VALUES (?, ?, ?)
                ''', (medicine_id, 1 if taken else 0, notes))
                
                # If taken, decrement doses_remaining
                if taken:
                    self.cursor.execute('''
                    UPDATE medicines
                    SET doses_remaining = doses_remaining - 1
                    WHERE id = ? AND doses_remaining IS NOT NULL AND doses_remaining > 0
                    ''', (medicine_id,))
                    
                self.connection.commit()
                log_id = self.cursor.lastrowid
            else:  # PostgreSQL
                self.cursor.execute('''
                INSERT INTO intake_logs (medicine_id, taken, notes)
                VALUES (%s, %s, %s) RETURNING id
                ''', (medicine_id, True if taken else False, notes))
                
                # Get the ID from the RETURNING clause
                log_id = self.cursor.fetchone()[0]
                
                # If taken, decrement doses_remaining
                if taken:
                    self.cursor.execute('''
                    UPDATE medicines
                    SET doses_remaining = doses_remaining - 1
                    WHERE id = %s AND doses_remaining IS NOT NULL AND doses_remaining > 0
                    ''', (medicine_id,))
                    
                self.connection.commit()
            
            # Update streak
            self._update_streak(taken)
            
            self.logger.info(f"Logged medicine intake: ID {medicine_id}, taken: {taken}")
            return log_id
            
        except (sqlite3.Error, psycopg2.Error) as e:
            self.logger.error(f"Error logging medicine intake: {str(e)}")
            self.connection.rollback()
            return None
            
    def _update_streak(self, taken):
        """
        Update the user's streak based on medicine intake.
        
        Args:
            taken (bool): Whether a medicine was taken today
        """
        try:
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            
            self.cursor.execute("SELECT * FROM streaks WHERE id = 1")
            row = self.cursor.fetchone()
            
            # Convert row to dictionary based on database type
            if self.db_type == 'sqlite':
                streak_data = dict(row)
            else:  # PostgreSQL
                columns = [desc[0] for desc in self.cursor.description]
                streak_data = dict(zip(columns, row))
            
            current_streak = streak_data.get('current_streak', 0)
            longest_streak = streak_data.get('longest_streak', 0)
            last_taken_date = streak_data.get('last_taken_date')
            
            if taken:
                # Check if this is a consecutive day
                if last_taken_date:
                    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                    
                    if last_taken_date == yesterday:
                        # Consecutive day
                        current_streak += 1
                    elif last_taken_date == today:
                        # Already taken today, no change
                        pass
                    else:
                        # Streak broken
                        current_streak = 1
                else:
                    # First time taking medicine
                    current_streak = 1
                    
                # Update longest streak if needed
                longest_streak = max(longest_streak, current_streak)
                
                # Update last taken date to today
                if self.db_type == 'sqlite':
                    self.cursor.execute('''
                    UPDATE streaks
                    SET current_streak = ?, longest_streak = ?, last_taken_date = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = 1
                    ''', (current_streak, longest_streak, today))
                else:  # PostgreSQL
                    self.cursor.execute('''
                    UPDATE streaks
                    SET current_streak = %s, longest_streak = %s, last_taken_date = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = 1
                    ''', (current_streak, longest_streak, today))
                
            self.connection.commit()
            
        except (sqlite3.Error, psycopg2.Error) as e:
            self.logger.error(f"Error updating streak: {str(e)}")
            self.connection.rollback()
            
    def get_streak(self):
        """
        Get the current and longest streaks.
        
        Returns:
            dict: Dictionary with current_streak and longest_streak
        """
        try:
            self.cursor.execute("SELECT current_streak, longest_streak FROM streaks WHERE id = 1")
            row = self.cursor.fetchone()
            
            if row:
                if self.db_type == 'sqlite':
                    return dict(row)
                else:  # PostgreSQL
                    columns = [desc[0] for desc in self.cursor.description]
                    return dict(zip(columns, row))
            else:
                return {'current_streak': 0, 'longest_streak': 0}
            
        except (sqlite3.Error, psycopg2.Error) as e:
            self.logger.error(f"Error getting streak: {str(e)}")
            return {'current_streak': 0, 'longest_streak': 0}
            
    def get_intake_logs(self, medicine_id=None, start_date=None, end_date=None):
        """
        Get medicine intake logs with optional filtering.
        
        Args:
            medicine_id (int, optional): Filter by medicine ID
            start_date (str, optional): Start date in YYYY-MM-DD format
            end_date (str, optional): End date in YYYY-MM-DD format
            
        Returns:
            list: List of log dictionaries
        """
        try:
            base_query = '''
            SELECT l.*, m.name as medicine_name
            FROM intake_logs l
            JOIN medicines m ON l.medicine_id = m.id
            '''
            
            conditions = []
            params = []
            placeholder = "?" if self.db_type == 'sqlite' else "%s"
            
            if medicine_id is not None:
                conditions.append(f"l.medicine_id = {placeholder}")
                params.append(medicine_id)
                
            if start_date:
                if self.db_type == 'sqlite':
                    conditions.append(f"DATE(l.intake_time) >= {placeholder}")
                else:  # PostgreSQL
                    conditions.append(f"DATE(l.intake_time) >= {placeholder}::date")
                params.append(start_date)
                
            if end_date:
                if self.db_type == 'sqlite':
                    conditions.append(f"DATE(l.intake_time) <= {placeholder}")
                else:  # PostgreSQL
                    conditions.append(f"DATE(l.intake_time) <= {placeholder}::date")
                params.append(end_date)
                
            query = base_query
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
                
            query += " ORDER BY l.intake_time DESC"
            
            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()
            
            # Convert to dictionaries based on database type
            if self.db_type == 'sqlite':
                return [dict(row) for row in rows]
            else:  # PostgreSQL
                columns = [desc[0] for desc in self.cursor.description]
                return [dict(zip(columns, row)) for row in rows]
            
        except (sqlite3.Error, psycopg2.Error) as e:
            self.logger.error(f"Error getting intake logs: {str(e)}")
            return []
            
    def save_setting(self, key, value):
        """
        Save a setting to the database.
        
        Args:
            key (str): Setting key
            value: Setting value (will be converted to JSON)
            
        Returns:
            bool: True if setting was saved successfully, False otherwise
        """
        try:
            # Convert value to JSON string
            json_value = json.dumps(value)
            
            if self.db_type == 'sqlite':
                self.cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ''', (key, json_value))
            else:  # PostgreSQL
                # Check if the setting already exists
                self.cursor.execute("SELECT 1 FROM settings WHERE key = %s", (key,))
                exists = self.cursor.fetchone()
                
                if exists:
                    self.cursor.execute('''
                    UPDATE settings 
                    SET value = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE key = %s
                    ''', (json_value, key))
                else:
                    self.cursor.execute('''
                    INSERT INTO settings (key, value, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ''', (key, json_value))
            
            self.connection.commit()
            self.logger.info(f"Saved setting: {key}")
            return True
            
        except (sqlite3.Error, psycopg2.Error) as e:
            self.logger.error(f"Error saving setting: {str(e)}")
            self.connection.rollback()
            return False
            
    def get_setting(self, key, default=None):
        """
        Get a setting from the database.
        
        Args:
            key (str): Setting key
            default: Default value if setting is not found
            
        Returns:
            The setting value or default if not found
        """
        try:
            if self.db_type == 'sqlite':
                self.cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            else:  # PostgreSQL
                self.cursor.execute("SELECT value FROM settings WHERE key = %s", (key,))
                
            row = self.cursor.fetchone()
            
            if row:
                # Parse the JSON value
                if self.db_type == 'sqlite':
                    return json.loads(row['value'])
                else:  # PostgreSQL
                    # PostgreSQL returns values based on column position
                    return json.loads(row[0])
            else:
                return default
                
        except (sqlite3.Error, psycopg2.Error, json.JSONDecodeError) as e:
            self.logger.error(f"Error getting setting {key}: {str(e)}")
            return default
            
    def get_badges(self):
        """
        Get earned badges based on streaks and medicine intake.
        
        Returns:
            list: List of earned badge dictionaries
        """
        try:
            badges = []
            streak_data = self.get_streak()
            
            # Streak badges
            current_streak = streak_data.get('current_streak', 0)
            longest_streak = streak_data.get('longest_streak', 0)
            
            streak_levels = [
                (3, "3-Day Streak", "Took medicines for 3 consecutive days"),
                (7, "Weekly Warrior", "Took medicines for a week straight"),
                (14, "Two-Week Triumph", "Maintained a two-week medicine streak"),
                (30, "Monthly Master", "Maintained a monthly medicine streak"),
                (90, "Quarterly Champion", "Maintained a 3-month medicine streak"),
                (180, "Half-Year Hero", "Maintained a 6-month medicine streak"),
                (365, "Annual Achiever", "Maintained a full year medicine streak")
            ]
            
            for days, name, description in streak_levels:
                if longest_streak >= days:
                    badges.append({
                        'name': name,
                        'description': description,
                        'category': 'streak',
                        'achieved': True
                    })
                else:
                    badges.append({
                        'name': name,
                        'description': description,
                        'category': 'streak',
                        'achieved': False,
                        'progress': min(100, int((current_streak / days) * 100))
                    })
                    
            # Count total medicines taken
            if self.db_type == 'sqlite':
                self.cursor.execute("SELECT COUNT(*) as count FROM intake_logs WHERE taken = 1")
                total_taken = self.cursor.fetchone()['count']
            else:  # PostgreSQL
                self.cursor.execute("SELECT COUNT(*) FROM intake_logs WHERE taken = TRUE")
                total_taken = self.cursor.fetchone()[0]
            
            intake_levels = [
                (10, "Getting Started", "Took 10 doses of medicine"),
                (50, "Committed to Health", "Took 50 doses of medicine"),
                (100, "Century Club", "Took 100 doses of medicine"),
                (500, "Medicine Master", "Took 500 doses of medicine"),
                (1000, "Health Guru", "Took 1000 doses of medicine")
            ]
            
            for count, name, description in intake_levels:
                if total_taken >= count:
                    badges.append({
                        'name': name,
                        'description': description,
                        'category': 'intake',
                        'achieved': True
                    })
                else:
                    badges.append({
                        'name': name,
                        'description': description,
                        'category': 'intake',
                        'achieved': False,
                        'progress': min(100, int((total_taken / count) * 100))
                    })
                    
            return badges
            
        except (sqlite3.Error, psycopg2.Error) as e:
            self.logger.error(f"Error getting badges: {str(e)}")
            return []
