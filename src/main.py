import os
import sys
import logging
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import messagebox

# Add src directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.gui import MedicineReminderApp
from src.utils.db_manager import DatabaseManager
from src.utils.notifier import Notifier
from src.utils.scanner import BarcodeScanner
from src.utils.telegram_bot import TelegramBot
from src.utils.cloud_sync import CloudSync
from src.utils.pharmacy_locator import PharmacyLocator
from src.utils.calendar_integration import GoogleCalendarIntegration
from src.utils.sheets_integration import GoogleSheetsIntegration

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("medicine_reminder.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class MedicineReminderSystem:
    """Main controller class for the Medicine Reminder Application"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.notifier = Notifier()
        self.scanner = BarcodeScanner()
        
        # Initialize Telegram bot if token is available
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_bot = TelegramBot(telegram_token) if telegram_token else None
        
        # Initialize cloud sync
        self.cloud_sync = CloudSync()
        
        # Initialize pharmacy locator
        self.pharmacy_locator = PharmacyLocator()
        
        # Initialize Google services
        self.calendar = GoogleCalendarIntegration()
        self.sheets = GoogleSheetsIntegration()
        
        # Create root window and initialize GUI
        self.root = tk.Tk()
        self.app = MedicineReminderApp(self.root, self)
        
        # Schedule reminders check on startup
        self.schedule_reminders()
        
    def run(self):
        """Start the application main loop"""
        try:
            self.root.mainloop()
        except Exception as e:
            logger.error(f"Application error: {e}")
            messagebox.showerror("Error", f"An error occurred: {e}")
    
    def schedule_reminders(self):
        """Check for upcoming reminders and schedule notifications"""
        try:
            # Get medicines with reminders in the next hour
            now = datetime.now()
            upcoming = self.db.get_upcoming_reminders(now, now + timedelta(hours=1))
            
            for medicine in upcoming:
                reminder_time = datetime.strptime(medicine['next_reminder'], '%Y-%m-%d %H:%M:%S')
                time_diff = (reminder_time - now).total_seconds()
                
                if time_diff > 0:
                    # Schedule notification
                    self.root.after(int(time_diff * 1000), 
                                   lambda m=medicine: self.send_reminder(m))
            
            # Schedule next check in 10 minutes
            self.root.after(600000, self.schedule_reminders)
            
        except Exception as e:
            logger.error(f"Error scheduling reminders: {e}")
    
    def send_reminder(self, medicine):
        """Send a reminder notification for a medicine"""
        try:
            # Send system notification
            self.notifier.send_system_notification(
                title=f"Medicine Reminder: {medicine['name']}",
                message=f"Time to take {medicine['dosage']} of {medicine['name']}"
            )
            
            # Send Telegram message if configured
            if self.telegram_bot and medicine.get('telegram_notify', False):
                chat_id = self.db.get_user_settings().get('telegram_chat_id')
                if chat_id:
                    self.telegram_bot.send_message(
                        chat_id=chat_id,
                        text=f"Medicine Reminder: Time to take {medicine['dosage']} of {medicine['name']}"
                    )
            
            # Update medicine reminder status
            self.db.update_reminder_status(medicine['id'])
            
            # Update reminder in Google Calendar if enabled
            if self.calendar.is_authenticated() and medicine.get('calendar_sync', False):
                self.calendar.update_reminder(medicine)
                
        except Exception as e:
            logger.error(f"Error sending reminder: {e}")

if __name__ == "__main__":
    app = MedicineReminderSystem()
    app.run()
