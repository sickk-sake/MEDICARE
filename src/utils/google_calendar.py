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

class GoogleCalendarIntegration:
    """
    Class to handle Google Calendar integration for medicine reminders.
    """
    
    def __init__(self, db_manager, token_path=None):
        """
        Initialize the Google Calendar integration.
        
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
        
        # Calendar ID for medicine reminders
        self.calendar_id = None
        self.calendar_name = "Medicine Reminders"
        
        # The file scope required for Google Calendar API
        self.SCOPES = ['https://www.googleapis.com/auth/calendar']
        
        # Credentials file path
        if token_path:
            self.token_path = token_path
        else:
            # Create a data directory for tokens if needed
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)
            self.token_path = os.path.join(data_dir, "calendar_token.json")
            
    def is_authenticated(self):
        """
        Check if the user is authenticated with Google Calendar.
        
        Returns:
            bool: True if authenticated, False otherwise
        """
        return self.credentials is not None and self.credentials.valid
        
    def authenticate(self):
        """
        Authenticate with Google Calendar using OAuth2.
        
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
            self.service = build('calendar', 'v3', credentials=creds)
            
            # Ensure the medicine calendar exists
            self._ensure_calendar_exists()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Authentication error: {str(e)}")
            return False
            
    def _ensure_calendar_exists(self):
        """
        Ensure that the medicine reminders calendar exists.
        Sets self.calendar_id with the calendar ID.
        """
        try:
            # List all calendars
            calendar_list = self.service.calendarList().list().execute()
            
            # Check if medicine calendar already exists
            for calendar in calendar_list.get('items', []):
                if calendar.get('summary') == self.calendar_name:
                    self.calendar_id = calendar['id']
                    self.logger.info(f"Found existing medicine calendar: {self.calendar_id}")
                    return
                    
            # Create a new calendar
            calendar = {
                'summary': self.calendar_name,
                'description': 'Calendar for medicine reminders',
                'timeZone': 'Etc/UTC'
            }
            
            created_calendar = self.service.calendars().insert(body=calendar).execute()
            self.calendar_id = created_calendar['id']
            self.logger.info(f"Created medicine calendar: {self.calendar_id}")
            
        except Exception as e:
            self.logger.error(f"Error ensuring calendar exists: {str(e)}")
            raise
            
    def create_reminder_event(self, medicine_name, dosage, reminder_time, notes=None, recurrence=None):
        """
        Create a calendar event for a medicine reminder.
        
        Args:
            medicine_name (str): Name of the medicine
            dosage (str): Dosage information
            reminder_time (datetime): Time for the reminder
            notes (str, optional): Additional notes
            recurrence (list, optional): List of RRULE strings for recurrence
            
        Returns:
            str: ID of the created event or None if error
        """
        try:
            if not self.service:
                if not self.authenticate():
                    return None
                    
            if not self.calendar_id:
                self._ensure_calendar_exists()
                
            # Format the event
            event = {
                'summary': f'Take {medicine_name}',
                'description': f'Dosage: {dosage}\n\n{notes if notes else ""}',
                'start': {
                    'dateTime': reminder_time.isoformat(),
                    'timeZone': 'Etc/UTC',
                },
                'end': {
                    'dateTime': (reminder_time + datetime.timedelta(minutes=30)).isoformat(),
                    'timeZone': 'Etc/UTC',
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': 15},
                        {'method': 'popup', 'minutes': 0}
                    ],
                }
            }
            
            # Add recurrence if specified
            if recurrence:
                event['recurrence'] = recurrence
                
            created_event = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event
            ).execute()
            
            self.logger.info(f"Created calendar event: {created_event.get('id')}")
            return created_event.get('id')
            
        except Exception as e:
            self.logger.error(f"Error creating reminder event: {str(e)}")
            return None
            
    def update_reminder_event(self, event_id, **kwargs):
        """
        Update an existing reminder event.
        
        Args:
            event_id (str): ID of the event to update
            **kwargs: Fields to update (medicine_name, dosage, reminder_time, notes, recurrence)
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            if not self.service:
                if not self.authenticate():
                    return False
                    
            # Get the existing event
            event = self.service.events().get(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            
            # Update the event with new values
            if 'medicine_name' in kwargs:
                event['summary'] = f'Take {kwargs["medicine_name"]}'
                
            if 'dosage' in kwargs or 'notes' in kwargs:
                dosage = kwargs.get('dosage', event['description'].split('\n')[0].replace('Dosage: ', ''))
                notes = kwargs.get('notes', event['description'].split('\n\n')[1] if '\n\n' in event['description'] else '')
                event['description'] = f'Dosage: {dosage}\n\n{notes}'
                
            if 'reminder_time' in kwargs:
                reminder_time = kwargs['reminder_time']
                event['start']['dateTime'] = reminder_time.isoformat()
                event['end']['dateTime'] = (reminder_time + datetime.timedelta(minutes=30)).isoformat()
                
            if 'recurrence' in kwargs:
                if kwargs['recurrence']:
                    event['recurrence'] = kwargs['recurrence']
                elif 'recurrence' in event:
                    del event['recurrence']
                    
            updated_event = self.service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            
            self.logger.info(f"Updated calendar event: {event_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating reminder event: {str(e)}")
            return False
            
    def delete_reminder_event(self, event_id):
        """
        Delete a reminder event.
        
        Args:
            event_id (str): ID of the event to delete
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            if not self.service:
                if not self.authenticate():
                    return False
                    
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            
            self.logger.info(f"Deleted calendar event: {event_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting reminder event: {str(e)}")
            return False
            
    def get_reminder_events(self, time_min=None, time_max=None, max_results=100):
        """
        Get reminder events from the calendar.
        
        Args:
            time_min (datetime, optional): Minimum time to retrieve events from
            time_max (datetime, optional): Maximum time to retrieve events to
            max_results (int, optional): Maximum number of events to retrieve
            
        Returns:
            list: List of event dictionaries
        """
        try:
            if not self.service:
                if not self.authenticate():
                    return []
                    
            if not self.calendar_id:
                self._ensure_calendar_exists()
                
            # Set default time range if not specified
            if time_min is None:
                time_min = datetime.datetime.utcnow()
            if time_max is None:
                time_max = time_min + datetime.timedelta(days=30)
                
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min.isoformat() + 'Z',
                timeMax=time_max.isoformat() + 'Z',
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            return events
            
        except Exception as e:
            self.logger.error(f"Error getting reminder events: {str(e)}")
            return []
            
    def sync_medicine_schedule(self):
        """
        Sync the medicine schedule from the database to Google Calendar.
        Creates, updates or deletes events as needed.
        
        Returns:
            bool: True if sync was successful, False otherwise
        """
        try:
            if not self.service:
                if not self.authenticate():
                    return False
                    
            if not self.calendar_id:
                self._ensure_calendar_exists()
                
            # Get all medicines and their schedules
            medicines = self.db_manager.get_all_medicines()
            
            # Create a mapping of medicine ID to event ID
            medicine_events = {}
            
            # Get existing events for the next 30 days
            time_min = datetime.datetime.utcnow()
            time_max = time_min + datetime.timedelta(days=30)
            events = self.get_reminder_events(time_min, time_max)
            
            # Delete obsolete events
            for event in events:
                event_id = event['id']
                medicine_name = event['summary'].replace('Take ', '')
                
                found = False
                for medicine in medicines:
                    if medicine['name'] == medicine_name:
                        found = True
                        medicine_events[medicine['id']] = event_id
                        break
                        
                if not found:
                    self.delete_reminder_event(event_id)
                    
            # Create or update events for medicines
            for medicine in medicines:
                medicine_id = medicine['id']
                medicine_name = medicine['name']
                dosage = medicine['dosage']
                notes = medicine['notes']
                
                # Get schedules for this medicine
                schedules = self.db_manager.get_schedules_for_medicine(medicine_id)
                
                for schedule in schedules:
                    time_str = schedule['time']
                    day_of_week = schedule['day_of_week']
                    
                    # Set up recurrence rule
                    recurrence = None
                    if day_of_week >= 0:  # Specific day of week
                        # Convert 0-6 (Monday-Sunday) to RRULE format (SU,MO,TU,WE,TH,FR,SA)
                        days = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
                        recurrence = [f'RRULE:FREQ=WEEKLY;BYDAY={days[day_of_week]}']
                    else:  # Every day
                        recurrence = ['RRULE:FREQ=DAILY']
                        
                    # Set up reminder time
                    hour, minute = map(int, time_str.split(':'))
                    now = datetime.datetime.utcnow()
                    reminder_time = datetime.datetime(
                        now.year, now.month, now.day, hour, minute, 0
                    )
                    
                    if medicine_id in medicine_events:
                        # Update existing event
                        self.update_reminder_event(
                            medicine_events[medicine_id],
                            medicine_name=medicine_name,
                            dosage=dosage,
                            reminder_time=reminder_time,
                            notes=notes,
                            recurrence=recurrence
                        )
                    else:
                        # Create new event
                        event_id = self.create_reminder_event(
                            medicine_name,
                            dosage,
                            reminder_time,
                            notes,
                            recurrence
                        )
                        if event_id:
                            medicine_events[medicine_id] = event_id
                            
            return True
            
        except Exception as e:
            self.logger.error(f"Error syncing medicine schedule: {str(e)}")
            return False
            
    def _run_sync(self, interval_minutes=60):
        """
        Run the sync process in a background thread.
        
        Args:
            interval_minutes (int): Time between sync attempts in minutes
        """
        self.logger.info(f"Starting calendar sync thread with {interval_minutes} minute interval")
        
        while not self.stop_flag.is_set():
            try:
                # Authenticate if needed
                if not self.service and not self.authenticate():
                    time.sleep(60)  # Wait a minute before retrying authentication
                    continue
                    
                # Sync the medicine schedule
                self.sync_medicine_schedule()
                
                # Sleep for the specified interval
                for _ in range(interval_minutes * 60):
                    if self.stop_flag.is_set():
                        break
                    time.sleep(1)
                    
            except Exception as e:
                self.logger.error(f"Error in calendar sync thread: {str(e)}")
                time.sleep(60)  # Wait a minute before retrying
                
    def start_sync(self, interval_minutes=60):
        """
        Start the automatic sync process in a background thread.
        
        Args:
            interval_minutes (int): Time between sync attempts in minutes
            
        Returns:
            bool: True if sync was started, False otherwise
        """
        if self.sync_thread is not None and self.sync_thread.is_alive():
            self.logger.warning("Calendar sync thread is already running")
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
