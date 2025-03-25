import os
import sys
import logging
import tkinter as tk
from tkinter import messagebox
import threading
import time
import datetime

# Add the parent directory to the path to be able to import src modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.db_manager import DatabaseManager
from src.utils.notifier import MedicineNotifier
from src.utils.telegram_bot import TelegramBot
from src.utils.cloud_sync import GoogleDriveSync
from src.utils.pharmacy_locator import PharmacyLocator
from src.utils.google_calendar import GoogleCalendarIntegration
from src.utils.google_sheets import GoogleSheetsIntegration
from src.gui import MedicineReminderApp

def setup_logging():
    """Set up logging configuration."""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
    
    # Ensure log directory exists
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    # Set up logging
    log_file = os.path.join(log_dir, "medicine_reminder.log")
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

def main():
    """Main entry point of the application."""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting Medicine Reminder Application")
    
    # Ensure data directory exists
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    
    # Initialize database
    db_path = os.path.join(data_dir, "medicine_database.db")
    db_manager = DatabaseManager(db_path)
    logger.info(f"Database initialized at {db_path}")
    
    # Initialize notifier
    notifier = MedicineNotifier(db_manager)
    
    # Configure email if environment variables are set
    email_sender = os.getenv("EMAIL_SENDER")
    email_password = os.getenv("EMAIL_PASSWORD")
    email_recipient = os.getenv("EMAIL_RECIPIENT")
    
    if email_sender and email_password and email_recipient:
        notifier.configure_email(email_sender, email_password, email_recipient)
        logger.info("Email notifications configured")
    
    # Initialize Telegram bot
    telegram_bot = TelegramBot(db_manager)
    if telegram_bot.is_configured():
        telegram_bot.start()
        logger.info("Telegram bot started")
    else:
        logger.warning("Telegram bot not configured (TELEGRAM_BOT_TOKEN environment variable not set)")
    
    # Initialize Google Drive sync
    drive_sync = GoogleDriveSync(db_manager.db_path)
    
    # Initialize Pharmacy Locator
    pharmacy_locator = PharmacyLocator()
    
    # Initialize Google Calendar integration
    calendar_integration = GoogleCalendarIntegration(db_manager)
    
    # Initialize Google Sheets integration
    sheets_integration = GoogleSheetsIntegration(db_manager)
    
    # Start the notification scheduler
    notifier.start_scheduler()
    logger.info("Notification scheduler started")
    
    # Create the GUI
    root = tk.Tk()
    app = MedicineReminderApp(
        root, 
        db_manager, 
        notifier, 
        telegram_bot, 
        drive_sync, 
        pharmacy_locator,
        calendar_integration,
        sheets_integration
    )
    
    # Set up application closing handler
    def on_closing():
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            logger.info("Shutting down application")
            # Stop background threads
            notifier.stop_scheduler()
            telegram_bot.stop()
            drive_sync.stop_sync()
            calendar_integration.stop_sync()
            sheets_integration.stop_sync()
            # Close database connection
            db_manager.close()
            # Destroy the GUI
            root.destroy()
            
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Start the GUI
    logger.info("Starting GUI")
    root.mainloop()

if __name__ == "__main__":
    main()
