import os
import logging
import requests
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class TelegramBot:
    """Telegram bot integration for medicine reminders"""
    
    def __init__(self, token=None):
        """
        Initialize the Telegram bot
        
        Args:
            token: Telegram Bot API token, if None will try to get from environment
        """
        # Get token from env if not provided
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        
        if not self.token:
            logger.warning("Telegram Bot token not provided. Telegram notifications are disabled.")
            self.enabled = False
        else:
            self.enabled = True
            self.api_url = f"https://api.telegram.org/bot{self.token}"
            logger.debug("Telegram Bot initialized")
            
            # Test the API token
            self._test_token()
    
    def _test_token(self):
        """Test the API token to ensure it's valid"""
        if not self.enabled:
            return False
            
        try:
            response = requests.get(f"{self.api_url}/getMe", timeout=5)
            if response.status_code == 200:
                bot_info = response.json()
                if bot_info.get("ok"):
                    bot_username = bot_info.get("result", {}).get("username")
                    logger.info(f"Telegram Bot authenticated as @{bot_username}")
                    return True
                else:
                    error = bot_info.get("description", "Unknown error")
                    logger.error(f"Telegram Bot authentication failed: {error}")
                    self.enabled = False
                    return False
            else:
                logger.error(f"Telegram Bot authentication failed: HTTP {response.status_code}")
                self.enabled = False
                return False
                
        except Exception as e:
            logger.error(f"Error testing Telegram Bot token: {e}")
            self.enabled = False
            return False
    
    def send_message(self, chat_id, text, parse_mode="HTML"):
        """
        Send a message to a Telegram chat
        
        Args:
            chat_id: Telegram chat ID
            text: Message text
            parse_mode: Message format (HTML, Markdown)
            
        Returns:
            Response JSON if successful, None otherwise
        """
        if not self.enabled:
            logger.warning("Telegram Bot is not enabled. Message not sent.")
            return None
            
        try:
            url = f"{self.api_url}/sendMessage"
            
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            
            response = requests.post(url, data=payload, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                logger.debug(f"Telegram message sent to chat {chat_id}")
                return result
            else:
                logger.error(f"Error sending Telegram message: HTTP {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return None
    
    def send_medicine_reminder(self, chat_id, medicine_data):
        """
        Send a formatted medicine reminder message
        
        Args:
            chat_id: Telegram chat ID
            medicine_data: Dictionary containing medicine details
            
        Returns:
            Response JSON if successful, None otherwise
        """
        if not self.enabled:
            return None
            
        try:
            # Format the message with HTML
            message = (
                f"<b>Medicine Reminder</b> 💊\n\n"
                f"<b>Medicine:</b> {medicine_data.get('name', 'Unknown')}\n"
                f"<b>Dosage:</b> {medicine_data.get('dosage', 'Unknown')}\n"
                f"<b>Time:</b> {datetime.now().strftime('%H:%M')}\n"
            )
            
            # Add expiry warning if close to expiry
            if 'expiry_date' in medicine_data:
                expiry_date = datetime.strptime(medicine_data['expiry_date'], '%Y-%m-%d')
                days_until_expiry = (expiry_date - datetime.now()).days
                
                if days_until_expiry <= 0:
                    message += f"\n⚠️ <b>WARNING:</b> This medicine has EXPIRED! ⚠️"
                elif days_until_expiry <= 30:
                    message += f"\n⚠️ <b>WARNING:</b> This medicine expires in {days_until_expiry} days!"
            
            # Add instructions if available
            if 'instructions' in medicine_data and medicine_data['instructions']:
                message += f"\n\n<i>Instructions:</i> {medicine_data['instructions']}"
            
            return self.send_message(chat_id, message)
            
        except Exception as e:
            logger.error(f"Error sending medicine reminder via Telegram: {e}")
            return None
    
    def send_expiry_alert(self, chat_id, medicines):
        """
        Send an alert about medicines that are expiring soon
        
        Args:
            chat_id: Telegram chat ID
            medicines: List of medicine dictionaries with expiry dates
            
        Returns:
            Response JSON if successful, None otherwise
        """
        if not self.enabled or not medicines:
            return None
            
        try:
            # Format the message with HTML
            message = f"<b>Medicine Expiry Alert</b> ⚠️\n\nThe following medicines are expiring soon:\n\n"
            
            for medicine in medicines:
                name = medicine.get('name', 'Unknown')
                expiry = medicine.get('expiry_date', 'Unknown')
                
                # Calculate days until expiry
                try:
                    expiry_date = datetime.strptime(expiry, '%Y-%m-%d')
                    days_until_expiry = (expiry_date - datetime.now()).days
                    
                    if days_until_expiry <= 0:
                        status = "EXPIRED"
                    else:
                        status = f"Expires in {days_until_expiry} days"
                        
                    message += f"• <b>{name}</b>: {expiry} ({status})\n"
                    
                except:
                    message += f"• <b>{name}</b>: {expiry}\n"
            
            message += "\nPlease check and replace these medicines if necessary."
            
            return self.send_message(chat_id, message)
            
        except Exception as e:
            logger.error(f"Error sending expiry alert via Telegram: {e}")
            return None
    
    def get_chat_updates(self, offset=None, timeout=30):
        """
        Get updates (messages) from users
        
        Args:
            offset: Update ID to start from
            timeout: Long polling timeout in seconds
            
        Returns:
            List of updates if successful, empty list otherwise
        """
        if not self.enabled:
            return []
            
        try:
            url = f"{self.api_url}/getUpdates"
            
            params = {
                "timeout": timeout
            }
            
            if offset is not None:
                params["offset"] = offset
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    return result.get("result", [])
                else:
                    logger.error(f"Error getting Telegram updates: {result.get('description')}")
                    return []
            else:
                logger.error(f"Error getting Telegram updates: HTTP {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting Telegram updates: {e}")
            return []
    
    def set_commands(self, commands):
        """
        Set bot commands in Telegram menu
        
        Args:
            commands: List of dictionaries with 'command' and 'description' keys
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
            
        try:
            url = f"{self.api_url}/setMyCommands"
            
            payload = {
                "commands": json.dumps(commands)
            }
            
            response = requests.post(url, data=payload)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    logger.debug("Telegram bot commands updated successfully")
                    return True
                else:
                    logger.error(f"Error setting Telegram commands: {result.get('description')}")
                    return False
            else:
                logger.error(f"Error setting Telegram commands: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error setting Telegram commands: {e}")
            return False
