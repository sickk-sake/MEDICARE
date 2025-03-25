import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import platform
import time
from datetime import datetime
import threading

logger = logging.getLogger(__name__)

class Notifier:
    """Notification system for medicine reminders"""
    
    def __init__(self):
        """Initialize the notification system"""
        self.os_name = platform.system()  # Windows, Darwin (macOS), or Linux
        logger.debug(f"Notifier initialized on {self.os_name}")
        
        # Initialize email settings from environment variables
        self.email_sender = os.getenv("EMAIL_SENDER", "")
        self.email_password = os.getenv("EMAIL_PASSWORD", "")
        self.email_server = os.getenv("EMAIL_SERVER", "smtp.gmail.com")
        self.email_port = int(os.getenv("EMAIL_PORT", "587"))
        
        # Keep track of active notifications
        self.active_notifications = {}
        
        # Start notification cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_notifications, daemon=True)
        self.cleanup_thread.start()
    
    def send_system_notification(self, title, message, sound=True):
        """
        Send a system notification
        
        Args:
            title: Notification title
            message: Notification message
            sound: Whether to play a sound (default: True)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Different notification methods based on OS
            if self.os_name == "Windows":
                return self._send_windows_notification(title, message, sound)
            elif self.os_name == "Darwin":  # macOS
                return self._send_macos_notification(title, message, sound)
            elif self.os_name == "Linux":
                return self._send_linux_notification(title, message, sound)
            else:
                logger.warning(f"System notifications not supported on {self.os_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending system notification: {e}")
            return False
    
    def _send_windows_notification(self, title, message, sound=True):
        """Send notification on Windows"""
        try:
            # Use Windows toast notifications via plyer
            from plyer import notification
            
            notification.notify(
                title=title,
                message=message,
                app_name="Medicine Reminder",
                timeout=10
            )
            
            # Store notification in active list with expiry time
            notification_id = f"{time.time()}"
            self.active_notifications[notification_id] = {
                "title": title,
                "message": message,
                "timestamp": datetime.now(),
                "expiry": datetime.now().timestamp() + 30  # 30 seconds expiry
            }
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending Windows notification: {e}")
            
            # Fallback to console notification
            print(f"\n[NOTIFICATION] {title}: {message}\n")
            return False
    
    def _send_macos_notification(self, title, message, sound=True):
        """Send notification on macOS"""
        try:
            # Use applescript via osascript
            import subprocess
            
            # Escape double quotes in the message and title
            message = message.replace('"', '\\"')
            title = title.replace('"', '\\"')
            
            script = f'display notification "{message}" with title "{title}"'
            if sound:
                script += ' sound name "Submarine"'  # macOS default sound
                
            subprocess.run(["osascript", "-e", script], check=True)
            
            # Store notification in active list
            notification_id = f"{time.time()}"
            self.active_notifications[notification_id] = {
                "title": title,
                "message": message,
                "timestamp": datetime.now(),
                "expiry": datetime.now().timestamp() + 30  # 30 seconds expiry
            }
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending macOS notification: {e}")
            
            # Fallback to console notification
            print(f"\n[NOTIFICATION] {title}: {message}\n")
            return False
    
    def _send_linux_notification(self, title, message, sound=True):
        """Send notification on Linux"""
        try:
            # Try using plyer first
            try:
                from plyer import notification
                
                notification.notify(
                    title=title,
                    message=message,
                    app_name="Medicine Reminder",
                    timeout=10
                )
                
                return True
                
            except ImportError:
                # Fallback to using notify-send via subprocess
                import subprocess
                
                # Escape characters for shell
                message = message.replace('"', '\\"')
                title = title.replace('"', '\\"')
                
                cmd = ["notify-send", title, message, "--icon=dialog-information"]
                if sound:
                    # Play sound with paplay if available (most desktop environments)
                    subprocess.Popen("paplay /usr/share/sounds/freedesktop/stereo/message.oga", 
                                   shell=True, stderr=subprocess.DEVNULL)
                
                subprocess.run(cmd, check=True)
                
                # Store notification in active list
                notification_id = f"{time.time()}"
                self.active_notifications[notification_id] = {
                    "title": title,
                    "message": message,
                    "timestamp": datetime.now(),
                    "expiry": datetime.now().timestamp() + 30  # 30 seconds expiry
                }
                
                return True
                
        except Exception as e:
            logger.error(f"Error sending Linux notification: {e}")
            
            # Fallback to console notification
            print(f"\n[NOTIFICATION] {title}: {message}\n")
            return False
    
    def send_email_notification(self, recipient, subject, body):
        """
        Send an email notification
        
        Args:
            recipient: Email recipient address
            subject: Email subject
            body: Email body (HTML or plain text)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.email_sender or not self.email_password:
            logger.warning("Email credentials not configured. Set EMAIL_SENDER and EMAIL_PASSWORD environment variables.")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email_sender
            msg['To'] = recipient
            msg['Subject'] = subject
            
            # Attach body
            msg.attach(MIMEText(body, 'html'))
            
            # Connect to server and send
            with smtplib.SMTP(self.email_server, self.email_port) as server:
                server.starttls()
                server.login(self.email_sender, self.email_password)
                server.send_message(msg)
            
            logger.info(f"Email notification sent to {recipient}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
            return False
    
    def schedule_notification(self, title, message, schedule_time, notify_methods=None):
        """
        Schedule a notification for future delivery
        
        Args:
            title: Notification title
            message: Notification message
            schedule_time: Datetime when notification should be sent
            notify_methods: List of notification methods ('system', 'email', 'telegram')
            
        Returns:
            Notification ID if scheduled successfully, None otherwise
        """
        if notify_methods is None:
            notify_methods = ['system']
            
        try:
            # Create unique notification ID
            notification_id = f"notify_{int(time.time())}_{hash(title) % 10000}"
            
            # Calculate seconds until notification
            now = datetime.now()
            delay_seconds = (schedule_time - now).total_seconds()
            
            if delay_seconds <= 0:
                logger.warning(f"Scheduled time {schedule_time} is in the past. Sending immediately.")
                self.send_system_notification(title, message)
                return notification_id
            
            # Create a timer thread to send the notification
            timer = threading.Timer(
                delay_seconds,
                self._send_scheduled_notification,
                args=[notification_id, title, message, notify_methods]
            )
            timer.daemon = True
            timer.start()
            
            logger.info(f"Notification scheduled for {schedule_time}")
            return notification_id
            
        except Exception as e:
            logger.error(f"Error scheduling notification: {e}")
            return None
    
    def _send_scheduled_notification(self, notification_id, title, message, notify_methods):
        """Send a scheduled notification via specified methods"""
        try:
            logger.debug(f"Sending scheduled notification {notification_id}")
            
            # Send via each requested method
            for method in notify_methods:
                if method == 'system':
                    self.send_system_notification(title, message)
                elif method == 'email':
                    # Would need recipient from somewhere
                    pass
                elif method == 'telegram':
                    # Would need chat_id from somewhere
                    pass
            
        except Exception as e:
            logger.error(f"Error sending scheduled notification: {e}")
    
    def _cleanup_notifications(self):
        """Clean up expired notifications periodically"""
        while True:
            try:
                current_time = datetime.now().timestamp()
                
                # Find expired notifications
                expired = [nid for nid, data in self.active_notifications.items() 
                          if data.get("expiry", 0) < current_time]
                
                # Remove expired
                for nid in expired:
                    self.active_notifications.pop(nid, None)
                
                # Sleep for a while
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in notification cleanup: {e}")
                time.sleep(60)  # Sleep longer if there was an error
