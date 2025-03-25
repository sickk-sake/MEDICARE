import os
import json
import logging
import datetime
import threading
import time
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

class GoogleSheetsIntegration:
    """
    Class to handle Google Sheets integration for medicine data management.
    """
    
    def __init__(self, db_manager, token_path=None):
        """
        Initialize the Google Sheets integration.
        
        Args:
            db_manager: Database manager instance to access medicine data
            token_path (str, optional): Path to store the token file
        """
        self.logger = logging.getLogger(__name__)
        self.db_manager = db_manager
        self.credentials = None
        self.service = None
        self.sync_thread = None
        self.stop_flag = threading.Event()
        
        # Spreadsheet IDs
        self.medicines_spreadsheet_id = None
        self.logs_spreadsheet_id = None
        
        # Spreadsheet names
        self.medicines_spreadsheet_name = "Medicine Tracker - Medicines"
        self.logs_spreadsheet_name = "Medicine Tracker - Logs"
        
        # The file scope required for Google Sheets API
        self.SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        
        # Credentials file path
        if token_path:
            self.token_path = token_path
        else:
            db_dir = os.path.dirname(db_manager.db_path)
            self.token_path = os.path.join(db_dir, "sheets_token.json")
            
    def is_authenticated(self):
        """
        Check if the user is authenticated with Google Sheets.
        
        Returns:
            bool: True if authenticated, False otherwise
        """
        return self.credentials is not None and self.credentials.valid
        
    def authenticate(self):
        """
        Authenticate with Google Sheets using OAuth2.
        
        Returns:
            bool: True if authentication was successful, False otherwise
        """
        try:
            creds = None
            
            # The file token.json stores the user's access and refresh tokens
            if os.path.exists(self.token_path):
                try:
                    creds = Credentials.from_authorized_user_info(
                        json.load(open(self.token_path, 'r')),
                        self.SCOPES
                    )
                except Exception as e:
                    self.logger.error(f"Error loading credentials: {str(e)}")
            
            # If no valid credentials available, let the user log in
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                    except Exception as e:
                        self.logger.error(f"Error refreshing credentials: {str(e)}")
                        # Remove invalid token file
                        if os.path.exists(self.token_path):
                            os.remove(self.token_path)
                        return False
                else:
                    # Get client secrets from environment variable
                    client_config = os.getenv("GOOGLE_CLIENT_CONFIG")
                    if not client_config:
                        self.logger.error("Google client configuration not found in environment variables")
                        return False
                        
                    client_config_dict = json.loads(client_config)
                    
                    flow = InstalledAppFlow.from_client_config(
                        client_config_dict, 
                        self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                
                # Save the credentials for the next run
                try:
                    with open(self.token_path, 'w') as token:
                        token.write(creds.to_json())
                except Exception as e:
                    self.logger.error(f"Error saving credentials: {str(e)}")
            
            self.credentials = creds
            self.service = build('sheets', 'v4', credentials=creds)
            self.drive_service = build('drive', 'v3', credentials=creds)
            
            # Ensure spreadsheets exist
            self._ensure_spreadsheets_exist()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Authentication error: {str(e)}")
            return False
            
    def _ensure_spreadsheets_exist(self):
        """
        Ensure that the medicines and logs spreadsheets exist.
        Sets spreadsheet IDs.
        """
        try:
            # Check if IDs are stored in database settings
            medicines_id = self.db_manager.get_setting('medicines_spreadsheet_id')
            logs_id = self.db_manager.get_setting('logs_spreadsheet_id')
            
            # Verify if spreadsheets with these IDs still exist
            if medicines_id:
                try:
                    self.service.spreadsheets().get(spreadsheetId=medicines_id).execute()
                    self.medicines_spreadsheet_id = medicines_id
                except Exception:
                    medicines_id = None
                    
            if logs_id:
                try:
                    self.service.spreadsheets().get(spreadsheetId=logs_id).execute()
                    self.logs_spreadsheet_id = logs_id
                except Exception:
                    logs_id = None
                    
            # Create medicines spreadsheet if needed
            if not medicines_id:
                spreadsheet = {
                    'properties': {
                        'title': self.medicines_spreadsheet_name
                    },
                    'sheets': [
                        {
                            'properties': {
                                'title': 'Medicines',
                                'gridProperties': {
                                    'rowCount': 1000,
                                    'columnCount': 10
                                }
                            }
                        },
                        {
                            'properties': {
                                'title': 'Schedule',
                                'gridProperties': {
                                    'rowCount': 1000,
                                    'columnCount': 5
                                }
                            }
                        }
                    ]
                }
                
                created_spreadsheet = self.service.spreadsheets().create(body=spreadsheet).execute()
                self.medicines_spreadsheet_id = created_spreadsheet['spreadsheetId']
                self.db_manager.save_setting('medicines_spreadsheet_id', self.medicines_spreadsheet_id)
                self.logger.info(f"Created medicines spreadsheet: {self.medicines_spreadsheet_id}")
                
                # Initialize headers in medicines sheet
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.medicines_spreadsheet_id,
                    range='Medicines!A1:G1',
                    valueInputOption='RAW',
                    body={
                        'values': [['ID', 'Name', 'Barcode', 'Dosage', 'Expiry Date', 'Doses Remaining', 'Notes']]
                    }
                ).execute()
                
                # Initialize headers in schedule sheet
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.medicines_spreadsheet_id,
                    range='Schedule!A1:D1',
                    valueInputOption='RAW',
                    body={
                        'values': [['ID', 'Medicine ID', 'Day of Week', 'Time']]
                    }
                ).execute()
                
            # Create logs spreadsheet if needed
            if not logs_id:
                spreadsheet = {
                    'properties': {
                        'title': self.logs_spreadsheet_name
                    },
                    'sheets': [
                        {
                            'properties': {
                                'title': 'Intake Logs',
                                'gridProperties': {
                                    'rowCount': 1000,
                                    'columnCount': 5
                                }
                            }
                        },
                        {
                            'properties': {
                                'title': 'Streaks',
                                'gridProperties': {
                                    'rowCount': 10,
                                    'columnCount': 3
                                }
                            }
                        }
                    ]
                }
                
                created_spreadsheet = self.service.spreadsheets().create(body=spreadsheet).execute()
                self.logs_spreadsheet_id = created_spreadsheet['spreadsheetId']
                self.db_manager.save_setting('logs_spreadsheet_id', self.logs_spreadsheet_id)
                self.logger.info(f"Created logs spreadsheet: {self.logs_spreadsheet_id}")
                
                # Initialize headers in intake logs sheet
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.logs_spreadsheet_id,
                    range='Intake Logs!A1:E1',
                    valueInputOption='RAW',
                    body={
                        'values': [['ID', 'Medicine ID', 'Medicine Name', 'Intake Time', 'Taken']]
                    }
                ).execute()
                
                # Initialize headers in streaks sheet
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.logs_spreadsheet_id,
                    range='Streaks!A1:C1',
                    valueInputOption='RAW',
                    body={
                        'values': [['Current Streak', 'Longest Streak', 'Last Taken Date']]
                    }
                ).execute()
                
        except Exception as e:
            self.logger.error(f"Error ensuring spreadsheets exist: {str(e)}")
            raise
            
    def export_medicines_to_sheets(self):
        """
        Export all medicines data to Google Sheets.
        
        Returns:
            bool: True if export was successful, False otherwise
        """
        try:
            if not self.service:
                if not self.authenticate():
                    return False
                    
            if not self.medicines_spreadsheet_id:
                self._ensure_spreadsheets_exist()
                
            # Get all medicines from database
            medicines = self.db_manager.get_all_medicines()
            
            # Prepare data for sheets
            medicine_rows = [
                [
                    medicine['id'],
                    medicine['name'],
                    medicine.get('barcode', ''),
                    medicine.get('dosage', ''),
                    medicine.get('expiry_date', ''),
                    medicine.get('doses_remaining', ''),
                    medicine.get('notes', '')
                ]
                for medicine in medicines
            ]
            
            # Add header row
            medicine_rows.insert(0, ['ID', 'Name', 'Barcode', 'Dosage', 'Expiry Date', 'Doses Remaining', 'Notes'])
            
            # Update medicines sheet
            self.service.spreadsheets().values().clear(
                spreadsheetId=self.medicines_spreadsheet_id,
                range='Medicines!A1:G1000'
            ).execute()
            
            self.service.spreadsheets().values().update(
                spreadsheetId=self.medicines_spreadsheet_id,
                range='Medicines!A1',
                valueInputOption='RAW',
                body={'values': medicine_rows}
            ).execute()
            
            # Get all schedules
            all_schedules = []
            for medicine in medicines:
                schedules = self.db_manager.get_schedules_for_medicine(medicine['id'])
                all_schedules.extend(schedules)
                
            # Prepare data for schedule sheet
            schedule_rows = [
                [
                    schedule['id'],
                    schedule['medicine_id'],
                    schedule['day_of_week'],
                    schedule['time']
                ]
                for schedule in all_schedules
            ]
            
            # Add header row
            schedule_rows.insert(0, ['ID', 'Medicine ID', 'Day of Week', 'Time'])
            
            # Update schedule sheet
            self.service.spreadsheets().values().clear(
                spreadsheetId=self.medicines_spreadsheet_id,
                range='Schedule!A1:D1000'
            ).execute()
            
            self.service.spreadsheets().values().update(
                spreadsheetId=self.medicines_spreadsheet_id,
                range='Schedule!A1',
                valueInputOption='RAW',
                body={'values': schedule_rows}
            ).execute()
            
            self.logger.info("Exported medicines data to Google Sheets")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exporting medicines to sheets: {str(e)}")
            return False
            
    def export_logs_to_sheets(self):
        """
        Export medicine intake logs to Google Sheets.
        
        Returns:
            bool: True if export was successful, False otherwise
        """
        try:
            if not self.service:
                if not self.authenticate():
                    return False
                    
            if not self.logs_spreadsheet_id:
                self._ensure_spreadsheets_exist()
                
            # Get all intake logs
            logs = self.db_manager.get_intake_logs()
            
            # Prepare data for intake logs sheet
            log_rows = [
                [
                    log['id'],
                    log['medicine_id'],
                    log['medicine_name'],
                    log['intake_time'],
                    'Yes' if log['taken'] else 'No'
                ]
                for log in logs
            ]
            
            # Add header row
            log_rows.insert(0, ['ID', 'Medicine ID', 'Medicine Name', 'Intake Time', 'Taken'])
            
            # Update intake logs sheet
            self.service.spreadsheets().values().clear(
                spreadsheetId=self.logs_spreadsheet_id,
                range='Intake Logs!A1:E1000'
            ).execute()
            
            self.service.spreadsheets().values().update(
                spreadsheetId=self.logs_spreadsheet_id,
                range='Intake Logs!A1',
                valueInputOption='RAW',
                body={'values': log_rows}
            ).execute()
            
            # Get streak data
            streak_data = self.db_manager.get_streak()
            
            # Update streaks sheet
            self.service.spreadsheets().values().clear(
                spreadsheetId=self.logs_spreadsheet_id,
                range='Streaks!A1:C10'
            ).execute()
            
            self.service.spreadsheets().values().update(
                spreadsheetId=self.logs_spreadsheet_id,
                range='Streaks!A1',
                valueInputOption='RAW',
                body={
                    'values': [
                        ['Current Streak', 'Longest Streak', 'Last Taken Date'],
                        [
                            streak_data['current_streak'],
                            streak_data['longest_streak'],
                            streak_data.get('last_taken_date', '')
                        ]
                    ]
                }
            ).execute()
            
            self.logger.info("Exported logs data to Google Sheets")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exporting logs to sheets: {str(e)}")
            return False
            
    def import_medicines_from_sheets(self):
        """
        Import medicines data from Google Sheets.
        
        Returns:
            bool: True if import was successful, False otherwise
        """
        try:
            if not self.service:
                if not self.authenticate():
                    return False
                    
            if not self.medicines_spreadsheet_id:
                self._ensure_spreadsheets_exist()
                
            # Get data from medicines sheet
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.medicines_spreadsheet_id,
                range='Medicines!A2:G1000'  # Skip header row
            ).execute()
            
            medicines_rows = result.get('values', [])
            
            # Get data from schedule sheet
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.medicines_spreadsheet_id,
                range='Schedule!A2:D1000'  # Skip header row
            ).execute()
            
            schedule_rows = result.get('values', [])
            
            # Process medicines data
            for row in medicines_rows:
                # Ensure row has enough columns
                if len(row) < 7:
                    row.extend([''] * (7 - len(row)))
                    
                try:
                    medicine_id = int(row[0])
                    name = row[1]
                    barcode = row[2] if row[2] else None
                    dosage = row[3] if row[3] else None
                    expiry_date = row[4] if row[4] else None
                    doses_remaining = int(row[5]) if row[5] and row[5].isdigit() else None
                    notes = row[6] if row[6] else None
                    
                    # Check if medicine exists
                    existing_medicine = self.db_manager.get_medicine_by_id(medicine_id)
                    
                    if existing_medicine:
                        # Update existing medicine
                        self.db_manager.update_medicine(
                            medicine_id,
                            name=name,
                            barcode=barcode,
                            dosage=dosage,
                            expiry_date=expiry_date,
                            doses_remaining=doses_remaining,
                            notes=notes
                        )
                    else:
                        # Add new medicine with specific ID
                        # This is a bit of a hack since SQLite doesn't easily allow specifying ID
                        self.db_manager.cursor.execute('''
                        INSERT INTO medicines (id, name, barcode, dosage, expiry_date, doses_remaining, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (medicine_id, name, barcode, dosage, expiry_date, doses_remaining, notes))
                        self.db_manager.connection.commit()
                        
                except Exception as e:
                    self.logger.error(f"Error processing medicine row {row}: {str(e)}")
                    
            # Process schedule data
            for row in schedule_rows:
                # Ensure row has enough columns
                if len(row) < 4:
                    row.extend([''] * (4 - len(row)))
                    
                try:
                    schedule_id = int(row[0])
                    medicine_id = int(row[1])
                    day_of_week = int(row[2])
                    time_str = row[3]
                    
                    # Check if medicine exists
                    if not self.db_manager.get_medicine_by_id(medicine_id):
                        self.logger.warning(f"Schedule refers to non-existent medicine ID {medicine_id}")
                        continue
                        
                    # Get all schedules for this medicine
                    existing_schedules = self.db_manager.get_schedules_for_medicine(medicine_id)
                    
                    # Check if this schedule exists
                    exists = False
                    for schedule in existing_schedules:
                        if schedule['id'] == schedule_id:
                            # Update existing schedule
                            self.db_manager.update_schedule(
                                schedule_id,
                                time=time_str,
                                day_of_week=day_of_week
                            )
                            exists = True
                            break
                            
                    if not exists:
                        # Add new schedule with specific ID
                        self.db_manager.cursor.execute('''
                        INSERT INTO schedule (id, medicine_id, day_of_week, time)
                        VALUES (?, ?, ?, ?)
                        ''', (schedule_id, medicine_id, day_of_week, time_str))
                        self.db_manager.connection.commit()
                        
                except Exception as e:
                    self.logger.error(f"Error processing schedule row {row}: {str(e)}")
                    
            self.logger.info("Imported medicines data from Google Sheets")
            return True
            
        except Exception as e:
            self.logger.error(f"Error importing medicines from sheets: {str(e)}")
            return False
            
    def _run_sync(self, interval_minutes=30):
        """
        Run the sync process in a background thread.
        
        Args:
            interval_minutes (int): Time between sync attempts in minutes
        """
        self.logger.info(f"Starting sheets sync thread with {interval_minutes} minute interval")
        
        while not self.stop_flag.is_set():
            try:
                # Authenticate if needed
                if not self.service and not self.authenticate():
                    time.sleep(60)  # Wait a minute before retrying authentication
                    continue
                    
                # Export data to sheets
                self.export_medicines_to_sheets()
                self.export_logs_to_sheets()
                
                # Sleep for the specified interval
                for _ in range(interval_minutes * 60):
                    if self.stop_flag.is_set():
                        break
                    time.sleep(1)
                    
            except Exception as e:
                self.logger.error(f"Error in sheets sync thread: {str(e)}")
                time.sleep(60)  # Wait a minute before retrying
                
    def start_sync(self, interval_minutes=30):
        """
        Start the automatic sync process in a background thread.
        
        Args:
            interval_minutes (int): Time between sync attempts in minutes
            
        Returns:
            bool: True if sync was started, False otherwise
        """
        if self.sync_thread is not None and self.sync_thread.is_alive():
            self.logger.warning("Sheets sync thread is already running")
            return False
            
        self.stop_flag.clear()
        self.sync_thread = threading.Thread(target=self._run_sync, args=(interval_minutes,))
        self.sync_thread.daemon = True
        self.sync_thread.start()
        return True
        
    def stop_sync(self):
        """
        Stop the automatic sync process.
        
        Returns:
            bool: True if sync was stopped, False if it wasn't running
        """
        if self.sync_thread is None or not self.sync_thread.is_alive():
            return False
            
        self.stop_flag.set()
        self.sync_thread.join(timeout=5.0)
        self.sync_thread = None
        return True
