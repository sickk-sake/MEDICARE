import os
import logging
import json
import base64
from openai import OpenAI

class XAIAssistant:
    """
    Class to handle AI features using xAI (Grok API).
    This class provides AI-powered capabilities for the Medicine Reminder App.
    """
    
    def __init__(self):
        """Initialize the XAI Assistant."""
        self.logger = logging.getLogger(__name__)
        
        # Get API key from environment variable
        self.api_key = os.environ.get("XAI_API_KEY")
        
        # Check if API key is available
        if not self.api_key:
            self.logger.warning("xAI API key not found in environment variables")
            self.client = None
        else:
            # Create a custom OpenAI client with the X.AI endpoint
            self.client = OpenAI(base_url="https://api.x.ai/v1", api_key=self.api_key)
    
    def is_configured(self):
        """Check if the assistant is properly configured with an API key."""
        return self.client is not None
    
    def analyze_medicine_info(self, medicine_name, dosage=None, notes=None):
        """
        Analyze medicine information and provide insights or potential interactions.
        
        Args:
            medicine_name (str): Name of the medicine
            dosage (str, optional): Dosage information
            notes (str, optional): Additional notes
            
        Returns:
            dict: Analysis results or None if error
        """
        if not self.is_configured():
            self.logger.error("xAI not configured")
            return None
            
        try:
            # Formulate a prompt for the AI
            prompt = f"Please analyze this medication information and provide usage advice, potential side effects, "\
                    f"and general information:\n\nMedicine: {medicine_name}"
            
            if dosage:
                prompt += f"\nDosage: {dosage}"
            
            if notes:
                prompt += f"\nAdditional Notes: {notes}"
                
            prompt += "\n\nProvide information in JSON format with the following structure: " \
                     "{'usage_advice': '...', 'side_effects': ['...', '...'], 'interactions': ['...'], 'general_info': '...'}"
            
            # Call the xAI API
            response = self.client.chat.completions.create(
                model="grok-2-1212",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            # Parse and return the response
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            self.logger.error(f"Error analyzing medicine: {str(e)}")
            return None
    
    def generate_reminder_message(self, medicine_name, dosage, time, is_important=False):
        """
        Generate a personalized reminder message for taking medicine.
        
        Args:
            medicine_name (str): Name of the medicine
            dosage (str): Dosage information
            time (str): Time to take the medicine
            is_important (bool): Whether this medicine is particularly important
            
        Returns:
            str: Personalized reminder message or default message if error
        """
        if not self.is_configured():
            # Return a default message if xAI is not configured
            if is_important:
                return f"IMPORTANT REMINDER: Time to take {medicine_name} ({dosage}) at {time}!"
            else:
                return f"Reminder: Time to take {medicine_name} ({dosage}) at {time}"
        
        try:
            # Formulate a prompt for the AI
            importance_level = "high" if is_important else "normal"
            
            prompt = f"Create a short, friendly reminder message for taking medicine. " \
                    f"Medicine: {medicine_name}, Dosage: {dosage}, Time: {time}, Importance: {importance_level}. " \
                    f"Keep it concise (max 100 characters) and motivational."
            
            # Call the xAI API
            response = self.client.chat.completions.create(
                model="grok-2-1212",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100
            )
            
            # Get the response text
            message = response.choices[0].message.content.strip()
            return message
            
        except Exception as e:
            self.logger.error(f"Error generating reminder message: {str(e)}")
            # Return a default message on error
            if is_important:
                return f"IMPORTANT REMINDER: Time to take {medicine_name} ({dosage}) at {time}!"
            else:
                return f"Reminder: Time to take {medicine_name} ({dosage}) at {time}"
    
    def identify_medicine_from_image(self, image_path):
        """
        Attempt to identify a medicine from an image.
        
        Args:
            image_path (str): Path to the image file
            
        Returns:
            dict: Identification results or None if error
        """
        if not self.is_configured():
            self.logger.error("xAI not configured")
            return None
            
        try:
            # Read and encode the image
            with open(image_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode("utf-8")
            
            # Call the vision model
            response = self.client.chat.completions.create(
                model="grok-2-vision-1212",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Please identify this medication and provide the following information in JSON format: " +
                                        "{'name': 'possible medicine name', 'description': 'brief description', " +
                                        "'confidence': 'high/medium/low', 'notes': 'any additional information'}"
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
                            }
                        ]
                    }
                ],
                response_format={"type": "json_object"}
            )
            
            # Parse and return the response
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            self.logger.error(f"Error identifying medicine from image: {str(e)}")
            return None
    
    def get_food_interactions(self, medicine_name):
        """
        Get potential food interactions for a medicine.
        
        Args:
            medicine_name (str): Name of the medicine
            
        Returns:
            list: List of potential food interactions or None if error
        """
        if not self.is_configured():
            self.logger.error("xAI not configured")
            return None
            
        try:
            prompt = f"Provide a list of potential food interactions for the medicine '{medicine_name}'. " \
                    f"Format the response as a JSON array of objects with 'food' and 'description' fields. " \
                    f"Include only scientifically verified interactions."
            
            response = self.client.chat.completions.create(
                model="grok-2-1212",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            # Parse the response
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting food interactions: {str(e)}")
            return None
    
    def suggest_alternative_medicines(self, medicine_name, reason=None):
        """
        Suggest alternative medicines for a given medicine.
        
        Args:
            medicine_name (str): Name of the medicine
            reason (str, optional): Reason for seeking alternatives
            
        Returns:
            list: List of alternative medicines or None if error
        """
        if not self.is_configured():
            self.logger.error("xAI not configured")
            return None
            
        try:
            prompt = f"Suggest potential alternative medications for '{medicine_name}'"
            
            if reason:
                prompt += f" for a patient who {reason}"
                
            prompt += ". Format the response as a JSON array of objects with 'name', 'class', and 'notes' fields. " \
                     "Include a clear disclaimer about consulting healthcare providers."
            
            response = self.client.chat.completions.create(
                model="grok-2-1212",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            # Parse the response
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            self.logger.error(f"Error suggesting alternative medicines: {str(e)}")
            return None