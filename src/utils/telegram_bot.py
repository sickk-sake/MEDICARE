import os
import logging
import threading
import time
import requests
from datetime import datetime, timedelta

class TelegramBot:
    """
    A class to handle Telegram bot integration for sending medicine reminders
    and receiving commands from users.
    """
    
    def __init__(self, db_manager):
        """
        Initialize the Telegram bot.
        
        Args:
            db_manager: Database manager instance to access medicine data
        """
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        
        # Get Telegram Bot API token from environment variable
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not self.token:
            self.logger.warning("Telegram Bot token not found in environment variables")
            
        self.chat_ids = set()  # Set of chat IDs to send notifications to
        self.bot_thread = None
        self.stop_flag = threading.Event()
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.last_update_id = 0
        
    def is_configured(self):
        """Check if the bot is properly configured."""
        return bool(self.token)
        
    def add_chat(self, chat_id):
        """
        Add a chat ID to send notifications to.
        
        Args:
            chat_id (int or str): Telegram chat ID
        """
        self.chat_ids.add(str(chat_id))
        self.logger.info(f"Added chat ID: {chat_id}")
        
    def remove_chat(self, chat_id):
        """
        Remove a chat ID from the notification list.
        
        Args:
            chat_id (int or str): Telegram chat ID
        """
        chat_id_str = str(chat_id)
        if chat_id_str in self.chat_ids:
            self.chat_ids.remove(chat_id_str)
            self.logger.info(f"Removed chat ID: {chat_id}")
        
    def send_message(self, chat_id, text):
        """
        Send a message to a specific chat.
        
        Args:
            chat_id (int or str): Telegram chat ID
            text (str): Message text
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        if not self.is_configured():
            self.logger.error("Telegram bot not configured")
            return False
            
        try:
            params = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'Markdown'
            }
            response = requests.post(f"{self.api_url}/sendMessage", params=params)
            
            if response.status_code == 200:
                return True
            else:
                self.logger.error(f"Failed to send Telegram message: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending Telegram message: {str(e)}")
            return False
            
    def broadcast_message(self, text):
        """
        Send a message to all registered chat IDs.
        
        Args:
            text (str): Message text
            
        Returns:
            int: Number of successfully sent messages
        """
        if not self.is_configured():
            self.logger.error("Telegram bot not configured")
            return 0
            
        success_count = 0
        for chat_id in self.chat_ids:
            if self.send_message(chat_id, text):
                success_count += 1
                
        return success_count
        
    def send_reminder(self, medicine_name, dosage, notes=None):
        """
        Send a medicine reminder to all registered chats.
        
        Args:
            medicine_name (str): Name of the medicine
            dosage (str): Dosage information
            notes (str, optional): Additional notes about the medicine
            
        Returns:
            int: Number of successfully sent reminders
        """
        current_time = datetime.now().strftime("%H:%M")
        
        message = (
            f"*Medicine Reminder*\n\n"
            f"Time to take: *{medicine_name}*\n"
            f"Dosage: {dosage}\n"
            f"Time: {current_time}"
        )
        
        if notes:
            message += f"\nNotes: {notes}"
            
        return self.broadcast_message(message)
        
    def send_expiry_alert(self, medicine_name, expiry_date):
        """
        Send a medicine expiry alert to all registered chats.
        
        Args:
            medicine_name (str): Name of the medicine
            expiry_date (str): Expiry date of the medicine
            
        Returns:
            int: Number of successfully sent alerts
        """
        message = (
            f"*Medicine Expiry Alert*\n\n"
            f"Medicine: *{medicine_name}*\n"
            f"Expiry Date: {expiry_date}\n\n"
            f"Please replace this medicine soon!"
        )
        
        return self.broadcast_message(message)
        
    def get_updates(self):
        """
        Get new message updates from Telegram.
        
        Returns:
            list: List of update objects or empty list if error
        """
        if not self.is_configured():
            return []
            
        try:
            params = {
                'offset': self.last_update_id + 1,
                'timeout': 30
            }
            response = requests.get(f"{self.api_url}/getUpdates", params=params)
            
            if response.status_code == 200:
                data = response.json()
                if data['ok'] and data['result']:
                    # Update the last update ID
                    self.last_update_id = max(update['update_id'] for update in data['result'])
                    return data['result']
                return []
            else:
                self.logger.error(f"Failed to get Telegram updates: {response.text}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error getting Telegram updates: {str(e)}")
            return []
            
    def process_command(self, message):
        """
        Process a command received from a Telegram user.
        
        Args:
            message (dict): Message object from Telegram
        """
        try:
            chat_id = message['chat']['id']
            text = message.get('text', '')
            
            if not text:
                return
                
            if text.startswith('/start'):
                self.add_chat(chat_id)
                self.send_message(chat_id, 
                    "Welcome to Medicine Reminder Bot!\n\n"
                    "I'll send you reminders when it's time to take your medicines.\n\n"
                    "Available commands:\n"
                    "/list - List all your medicines\n"
                    "/today - See today's schedule\n"
                    "/expiring - List medicines about to expire\n"
                    "/stop - Stop receiving notifications"
                )
                
            elif text.startswith('/stop'):
                self.remove_chat(chat_id)
                self.send_message(chat_id, "You've been unsubscribed from notifications.")
                
            elif text.startswith('/list'):
                medicines = self.db_manager.get_all_medicines()
                if not medicines:
                    self.send_message(chat_id, "You don't have any medicines in your database.")
                    return
                    
                message = "*Your Medicines*\n\n"
                for med in medicines:
                    message += f"• *{med['name']}* - {med['dosage']}\n"
                    
                self.send_message(chat_id, message)
                
            elif text.startswith('/today'):
                today = datetime.now().strftime("%Y-%m-%d")
                schedule = self.db_manager.get_medicines_for_date(today)
                
                if not schedule:
                    self.send_message(chat_id, "You don't have any medicines scheduled for today.")
                    return
                    
                message = "*Today's Medicine Schedule*\n\n"
                for med in schedule:
                    message += f"• *{med['time']}* - {med['name']} ({med['dosage']})\n"
                    
                self.send_message(chat_id, message)
                
            elif text.startswith('/expiring'):
                expiring = self.db_manager.get_expiring_medicines(days=30)
                
                if not expiring:
                    self.send_message(chat_id, "You don't have any medicines expiring soon.")
                    return
                    
                message = "*Medicines Expiring Soon*\n\n"
                for med in expiring:
                    message += f"• *{med['name']}* - Expires on {med['expiry_date']}\n"
                    
                self.send_message(chat_id, message)
                
            else:
                self.send_message(chat_id,
                    "Sorry, I don't understand that command.\n\n"
                    "Available commands:\n"
                    "/list - List all your medicines\n"
                    "/today - See today's schedule\n"
                    "/expiring - List medicines about to expire\n"
                    "/stop - Stop receiving notifications"
                )
                
        except Exception as e:
            self.logger.error(f"Error processing Telegram command: {str(e)}")
            
    def _run_bot(self):
        """
        Run the bot's message handling loop in a separate thread.
        """
        self.logger.info("Telegram bot thread started")
        
        while not self.stop_flag.is_set():
            try:
                updates = self.get_updates()
                
                for update in updates:
                    if 'message' in update:
                        self.process_command(update['message'])
                        
                # Check if there are any current medicine reminders to send
                now = datetime.now()
                current_time = now.strftime("%H:%M")
                
                # Get medicines that should be taken now
                medicines = self.db_manager.get_medicines_for_time(current_time)
                
                # Send reminders
                for medicine in medicines:
                    self.send_reminder(
                        medicine_name=medicine['name'],
                        dosage=medicine['dosage'],
                        notes=medicine.get('notes')
                    )
                    
                # Check for expiring medicines once a day
                if now.hour == 9 and now.minute == 0:
                    expiring = self.db_manager.get_expiring_medicines(days=7)
                    for medicine in expiring:
                        self.send_expiry_alert(
                            medicine_name=medicine['name'],
                            expiry_date=medicine['expiry_date']
                        )
                        
                # Sleep for a bit before next check
                time.sleep(10)
                
            except Exception as e:
                self.logger.error(f"Error in Telegram bot thread: {str(e)}")
                time.sleep(30)  # Sleep longer on error
                
    def start(self):
        """
        Start the Telegram bot in a background thread.
        """
        if not self.is_configured():
            self.logger.warning("Cannot start Telegram bot: not configured")
            return False
            
        if self.bot_thread is not None and self.bot_thread.is_alive():
            self.logger.warning("Telegram bot already running")
            return False
            
        self.stop_flag.clear()
        self.bot_thread = threading.Thread(target=self._run_bot)
        self.bot_thread.daemon = True
        self.bot_thread.start()
        self.logger.info("Telegram bot started")
        return True
        
    def stop(self):
        """
        Stop the Telegram bot.
        """
        if self.bot_thread is not None:
            self.stop_flag.set()
            self.bot_thread.join(timeout=5.0)
            self.bot_thread = None
            self.logger.info("Telegram bot stopped")
