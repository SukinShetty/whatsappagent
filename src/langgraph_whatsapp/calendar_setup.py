import os
import logging
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import pickle

logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    """Get a Google Calendar service object for making API calls."""
    creds = None
    # The file token.pickle stores the user's access and refresh tokens
    token_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'token.pickle')
    credentials_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'credentials.json')
    
    # Ensure the data directory exists
    os.makedirs(os.path.dirname(token_file), exist_ok=True)
    
    # Check if token.pickle exists with saved credentials
    if os.path.exists(token_file):
        logger.info(f"Loading credentials from {token_file}")
        try:
            with open(token_file, 'rb') as token:
                creds = pickle.load(token)
        except Exception as e:
            logger.error(f"Error loading token file: {e}")
    
    # If no valid credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired credentials")
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.error(f"Error refreshing credentials: {e}")
                creds = None
        
        if not creds:
            if not os.path.exists(credentials_file):
                logger.error(f"Credentials file not found at {credentials_file}")
                logger.error("Please download credentials.json from Google Cloud Console")
                logger.error("1. Go to https://console.cloud.google.com/")
                logger.error("2. Create a project and enable Google Calendar API")
                logger.error("3. Create OAuth credentials and download as credentials.json")
                logger.error("4. Place the file in the data directory")
                return None
                
            logger.info(f"Getting fresh credentials using {credentials_file}")
            try:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e:
                logger.error(f"Error during authentication flow: {e}")
                return None
                
            # Save the credentials for the next run
            with open(token_file, 'wb') as token:
                pickle.dump(creds, token)
                logger.info(f"Saved credentials to {token_file}")
    
    try:
        service = build('calendar', 'v3', credentials=creds)
        logger.info("Google Calendar service created successfully")
        return service
    except Exception as e:
        logger.error(f"Error building calendar service: {e}")
        return None

def setup_google_calendar():
    """Validate Google Calendar API access."""
    logger.info("Setting up Google Calendar API access")
    service = get_calendar_service()
    
    if service:
        try:
            # Try a simple API call to verify credentials
            now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
            events_result = service.events().list(
                calendarId='primary', 
                timeMin=now,
                maxResults=1,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            logger.info("Google Calendar API access verified successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to verify Google Calendar API access: {e}")
            return False
    else:
        logger.error("Failed to get Google Calendar service")
        return False

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    # Test the setup
    setup_google_calendar() 