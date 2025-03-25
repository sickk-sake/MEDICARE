import os
import json
import logging
import time
import threading
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import io

class GoogleDriveSync:
    """
    Class to handle syncing the medicine database with Google Drive.
    """
    
    def __init__(self, db_path="../data/medicine_database.db"):
        """
        Initialize the Google Drive sync handler.
        
        Args:
            db_path (str): Path to the local SQLite database
        """
        self.logger = logging.getLogger(__name__)
        self.db_path = db_path
        self.credentials = None
        self.service = None
        self.sync_thread = None
        self.stop_flag = threading.Event()
        
        # Folder and file IDs in Google Drive
        self.app_folder_id = None
        self.db_file_id = None
        
        # The file scope required for Google Drive API
        self.SCOPES = ['https://www.googleapis.com/auth/drive.file']
        
        # Folder name in Google Drive
        self.FOLDER_NAME = 'MedicineReminderApp'
        
        # Credentials file path
        self.token_path = os.path.join(os.path.dirname(db_path), "token.json")
        
    def is_authenticated(self):
        """
        Check if the user is authenticated with Google Drive.
        
        Returns:
            bool: True if authenticated, False otherwise
        """
        return self.credentials is not None and self.credentials.valid
        
    def authenticate(self):
        """
        Authenticate with Google Drive using OAuth2.
        
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
            self.service = build('drive', 'v3', credentials=creds)
            
            # Ensure the app folder exists
            self._ensure_app_folder_exists()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Authentication error: {str(e)}")
            return False
            
    def _ensure_app_folder_exists(self):
        """
        Ensure that the application folder exists in Google Drive.
        Sets self.app_folder_id with the folder ID.
        """
        try:
            # Search for existing folder
            results = self.service.files().list(
                q=f"name='{self.FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            items = results.get('files', [])
            
            if items:
                # Folder exists, use its ID
                self.app_folder_id = items[0]['id']
                self.logger.info(f"Found existing app folder: {self.app_folder_id}")
            else:
                # Create a new folder
                folder_metadata = {
                    'name': self.FOLDER_NAME,
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                
                folder = self.service.files().create(
                    body=folder_metadata,
                    fields='id'
                ).execute()
                
                self.app_folder_id = folder.get('id')
                self.logger.info(f"Created app folder: {self.app_folder_id}")
                
        except Exception as e:
            self.logger.error(f"Error ensuring app folder exists: {str(e)}")
            raise
            
    def _get_db_file_id(self):
        """
        Get the ID of the database file in Google Drive.
        
        Returns:
            str: File ID or None if not found
        """
        try:
            if not self.app_folder_id:
                self._ensure_app_folder_exists()
                
            # Get the database filename from the path
            db_filename = os.path.basename(self.db_path)
            
            # Search for the file in the app folder
            results = self.service.files().list(
                q=f"name='{db_filename}' and '{self.app_folder_id}' in parents and trashed=false",
                spaces='drive',
                fields='files(id, name, modifiedTime)'
            ).execute()
            
            items = results.get('files', [])
            
            if items:
                self.db_file_id = items[0]['id']
                return items[0]['id']
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting database file ID: {str(e)}")
            return None
            
    def upload_database(self):
        """
        Upload the local database to Google Drive.
        
        Returns:
            bool: True if upload was successful, False otherwise
        """
        try:
            if not self.service:
                if not self.authenticate():
                    return False
                    
            if not self.app_folder_id:
                self._ensure_app_folder_exists()
                
            # Get the database filename from the path
            db_filename = os.path.basename(self.db_path)
            
            # Prepare metadata for the file
            file_metadata = {
                'name': db_filename,
                'parents': [self.app_folder_id]
            }
            
            # Create a temporary copy of the database
            temp_db_path = f"{self.db_path}.temp"
            shutil.copy2(self.db_path, temp_db_path)
            
            try:
                # Prepare the file to upload
                media = MediaFileUpload(
                    temp_db_path,
                    mimetype='application/x-sqlite3',
                    resumable=True
                )
                
                # Check if the file already exists
                file_id = self._get_db_file_id()
                
                if file_id:
                    # Update existing file
                    file = self.service.files().update(
                        fileId=file_id,
                        body=file_metadata,
                        media_body=media,
                        fields='id'
                    ).execute()
                    self.logger.info(f"Updated database file: {file.get('id')}")
                else:
                    # Create new file
                    file = self.service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id'
                    ).execute()
                    self.db_file_id = file.get('id')
                    self.logger.info(f"Uploaded database file: {file.get('id')}")
            finally:
                # Delete the temporary file
                if os.path.exists(temp_db_path):
                    os.remove(temp_db_path)
                    
            return True
            
        except Exception as e:
            self.logger.error(f"Error uploading database: {str(e)}")
            return False
            
    def download_database(self):
        """
        Download the database from Google Drive.
        
        Returns:
            bool: True if download was successful, False otherwise
        """
        try:
            if not self.service:
                if not self.authenticate():
                    return False
                    
            # Get the file ID if not already known
            file_id = self.db_file_id or self._get_db_file_id()
            
            if not file_id:
                self.logger.warning("No database file found in Google Drive")
                return False
                
            # Download the file
            request = self.service.files().get_media(fileId=file_id)
            file_handle = io.BytesIO()
            downloader = MediaIoBaseDownload(file_handle, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
                
            # Backup the current database
            if os.path.exists(self.db_path):
                backup_path = f"{self.db_path}.backup"
                shutil.copy2(self.db_path, backup_path)
                
            # Save the downloaded file
            with open(self.db_path, 'wb') as f:
                f.write(file_handle.getvalue())
                
            self.logger.info("Downloaded database file successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error downloading database: {str(e)}")
            return False
            
    def compare_databases(self):
        """
        Compare the local and remote database timestamps.
        
        Returns:
            int: 1 if local is newer, -1 if remote is newer, 0 if same age or error
        """
        try:
            if not self.service:
                if not self.authenticate():
                    return 0
                    
            # Get the file ID and metadata
            file_id = self.db_file_id or self._get_db_file_id()
            
            if not file_id:
                # No remote database, local is newer
                return 1
                
            # Get the file metadata
            file = self.service.files().get(
                fileId=file_id,
                fields='modifiedTime'
            ).execute()
            
            remote_modified = datetime.fromisoformat(file['modifiedTime'].replace('Z', '+00:00'))
            
            # Get local file modification time
            local_modified = datetime.fromtimestamp(os.path.getmtime(self.db_path))
            
            # Compare timestamps
            if local_modified > remote_modified:
                return 1  # Local is newer
            elif remote_modified > local_modified:
                return -1  # Remote is newer
            else:
                return 0  # Same age
                
        except Exception as e:
            self.logger.error(f"Error comparing databases: {str(e)}")
            return 0
            
    def _run_sync(self, interval_minutes=15):
        """
        Run the sync process in a background thread.
        
        Args:
            interval_minutes (int): Time between sync attempts in minutes
        """
        self.logger.info(f"Starting sync thread with {interval_minutes} minute interval")
        
        while not self.stop_flag.is_set():
            try:
                # Authenticate if needed
                if not self.service and not self.authenticate():
                    time.sleep(60)  # Wait a minute before retrying authentication
                    continue
                    
                # Compare databases
                comparison = self.compare_databases()
                
                if comparison > 0:
                    # Local is newer, upload
                    self.logger.info("Local database is newer, uploading...")
                    self.upload_database()
                elif comparison < 0:
                    # Remote is newer, download
                    self.logger.info("Remote database is newer, downloading...")
                    self.download_database()
                else:
                    self.logger.info("Databases are in sync")
                    
                # Sleep for the specified interval
                for _ in range(interval_minutes * 60):
                    if self.stop_flag.is_set():
                        break
                    time.sleep(1)
                    
            except Exception as e:
                self.logger.error(f"Error in sync thread: {str(e)}")
                time.sleep(60)  # Wait a minute before retrying
                
    def start_sync(self, interval_minutes=15):
        """
        Start the automatic sync process in a background thread.
        
        Args:
            interval_minutes (int): Time between sync attempts in minutes
            
        Returns:
            bool: True if sync was started, False otherwise
        """
        if self.sync_thread is not None and self.sync_thread.is_alive():
            self.logger.warning("Sync thread is already running")
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
        
    def force_sync(self, upload=True):
        """
        Force an immediate sync operation.
        
        Args:
            upload (bool): True to upload local database, False to download remote
            
        Returns:
            bool: True if sync was successful, False otherwise
        """
        try:
            if not self.service and not self.authenticate():
                return False
                
            if upload:
                return self.upload_database()
            else:
                return self.download_database()
                
        except Exception as e:
            self.logger.error(f"Error during force sync: {str(e)}")
            return False
