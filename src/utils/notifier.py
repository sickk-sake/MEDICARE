import os
import logging
import datetime
import schedule
import time
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from plyer import notification

class MedicineNotifier:
    """
    A class to handle medication reminders via different notification channels:
    - System notifications
    - Email
    
    Telegram notifications are handled in telegram_bot.py
    """
    
    def __init__(self, db_manager):
        """
        Initialize the notifier with a database manager.
        
        Args:
            db_manager: Database manager instance to access medicine data
        """
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        self.notification_thread = None
        self.stop_flag = threading.Event()
        
        # Email configuration
        self.email_enabled = False
        self.email_sender = ""
        self.email_password = ""
        self.email_recipient = ""
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        
    def configure_email(self, sender, password, recipient, server="smtp.gmail.com", port=587):
        """
        Configure email notification settings.
        
        Args:
            sender (str): Sender email address
            password (str): Sender email password or app password
            recipient (str): Recipient email address
            server (str): SMTP server address
            port (int): SMTP server port
        """
        self.email_sender = sender
        self.email_password = password
        self.email_recipient = recipient
        self.smtp_server = server
        self.smtp_port = port
        self.email_enabled = True
        self.logger.info("Email notifications configured")
        
    def send_system_notification(self, title, message, timeout=10):
        """
        Send a system notification.
        
        Args:
            title (str): Notification title
            message (str): Notification message
            timeout (int): Notification timeout in seconds
            
        Returns:
            bool: True if notification was sent successfully, False otherwise
        """
        try:
            notification.notify(
                title=title,
                message=message,
                app_name="Medicine Reminder",
                timeout=timeout
            )
            return True
        except Exception as e:
            self.logger.error(f"Failed to send system notification: {str(e)}")
            return False
            
    def send_email_notification(self, subject, message):
        """
        Send an email notification.
        
        Args:
            subject (str): Email subject
            message (str): Email message
            
        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        if not self.email_enabled:
            self.logger.warning("Email notifications not configured")
            return False
            
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_sender
            msg['To'] = self.email_recipient
            msg['Subject'] = subject
            
            msg.attach(MIMEText(message, 'plain'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_sender, self.email_password)
                server.send_message(msg)
                
            self.logger.info(f"Email notification sent to {self.email_recipient}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send email notification: {str(e)}")
            return False
            
    def check_medicine_schedule(self):
        """
        Check which medicines should be taken now and send notifications.
        """
        try:
            now = datetime.datetime.now()
            current_time = now.strftime("%H:%M")
            current_date = now.strftime("%Y-%m-%d")
            
            # Get medicines with reminders scheduled for current time
            medicines = self.db_manager.get_medicines_for_time(current_time)
            
            for medicine in medicines:
                name = medicine["name"]
                dosage = medicine["dosage"]
                
                # Skip if medicine has expired
                if medicine["expiry_date"] < current_date:
                    continue
                    
                # Determine if this is the last dose
                doses_remaining = medicine.get("doses_remaining")
                last_dose_warning = ""
                if doses_remaining is not None and doses_remaining <= 3:
                    last_dose_warning = f" (Only {doses_remaining} dose(s) remaining!)"
                
                # Send system notification
                title = f"Medicine Reminder: {name}"
                message = f"Time to take {name} - {dosage}{last_dose_warning}"
                self.send_system_notification(title, message)
                
                # Send email notification if enabled
                if self.email_enabled:
                    email_subject = f"Medicine Reminder: {name}"
                    email_message = (
                        f"Dear User,\n\n"
                        f"This is a reminder to take your medicine: {name}\n"
                        f"Dosage: {dosage}\n"
                        f"{last_dose_warning}\n\n"
                        f"Time: {current_time}\n"
                        f"Date: {current_date}\n\n"
                        f"Stay healthy!\n"
                        f"Your Medicine Reminder App"
                    )
                    self.send_email_notification(email_subject, email_message)
                    
        except Exception as e:
            self.logger.error(f"Error checking medicine schedule: {str(e)}")
            
    def check_expiring_medicines(self):
        """
        Check for medicines that are about to expire and send notifications.
        """
        try:
            # Get medicines expiring in the next 7 days
            expiring_medicines = self.db_manager.get_expiring_medicines(days=7)
            
            if not expiring_medicines:
                return
                
            # Group medicines by expiry date
            by_date = {}
            for medicine in expiring_medicines:
                expiry = medicine["expiry_date"]
                if expiry not in by_date:
                    by_date[expiry] = []
                by_date[expiry].append(medicine["name"])
                
            # Send notifications for each expiry date
            for expiry_date, names in by_date.items():
                medicine_list = ", ".join(names)
                
                # System notification
                title = "Medicine Expiry Warning"
                message = f"Medicines expiring on {expiry_date}: {medicine_list}"
                self.send_system_notification(title, message, timeout=15)
                
                # Email notification
                if self.email_enabled:
                    email_subject = "Medicine Expiry Warning"
                    email_message = (
                        f"Dear User,\n\n"
                        f"The following medicines will expire on {expiry_date}:\n"
                        f"{medicine_list}\n\n"
                        f"Please consider replacing them soon.\n\n"
                        f"Your Medicine Reminder App"
                    )
                    self.send_email_notification(email_subject, email_message)
                    
        except Exception as e:
            self.logger.error(f"Error checking expiring medicines: {str(e)}")
            
    def _run_scheduler(self):
        """
        Run the scheduler in a separate thread.
        """
        # Schedule medicine reminders to run every minute
        schedule.every(1).minutes.do(self.check_medicine_schedule)
        
        # Schedule expiry check to run once a day
        schedule.every().day.at("09:00").do(self.check_expiring_medicines)
        
        while not self.stop_flag.is_set():
            schedule.run_pending()
            time.sleep(10)  # Sleep for 10 seconds before next check
            
    def start_scheduler(self):
        """
        Start the notification scheduler in a background thread.
        """
        if self.notification_thread is not None and self.notification_thread.is_alive():
            self.logger.warning("Notification scheduler already running")
            return
            
        self.stop_flag.clear()
        self.notification_thread = threading.Thread(target=self._run_scheduler)
        self.notification_thread.daemon = True
        self.notification_thread.start()
        self.logger.info("Notification scheduler started")
        
    def stop_scheduler(self):
        """
        Stop the notification scheduler.
        """
        if self.notification_thread is not None:
            self.stop_flag.set()
            self.notification_thread.join(timeout=5.0)
            self.notification_thread = None
            self.logger.info("Notification scheduler stopped")
