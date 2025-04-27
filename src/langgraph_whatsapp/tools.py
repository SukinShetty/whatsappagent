import sqlite3
import os
import logging
import re
from typing import List, Optional, Dict, Any
from datetime import datetime
import dateparser
from twilio.rest import Client
from apscheduler.schedulers.background import BackgroundScheduler
from src.langgraph_whatsapp.db import get_db_connection

logger = logging.getLogger(__name__)

def extract_links(text: str) -> List[str]:
    """Extracts URLs from text content."""
    if not text:
        return []
    
    # URL regex pattern - more comprehensive to catch more complex URLs
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?:/[-\w%/.\[\]~!$&\'()*+,;=:@]*)*/?' 
    
    # Extract all URLs using the better pattern
    urls = re.findall(url_pattern, text)
    
    # Expand github.com URLs that might have been shortened
    for i, url in enumerate(urls):
        if 'github.com' in url and '/SkyworkAI/' in url:
            # Make sure we capture the full SkyReels URL
            if not url.endswith('SkyReels-V2'):
                if 'SkyReels-V2' in url:
                    # Trim any extra content after the repo name
                    url = url[:url.find('SkyReels-V2') + len('SkyReels-V2')]
                    urls[i] = url
    
    logger.debug(f"Extracted URLs: {urls}")
    return urls

def save_link(user_id: str, link: str) -> str:
    """Saves a provided link for the user."""
    if not user_id or not link:
        return "Error: Both user_id and link are required."
    
    # Simple URL validation
    if not (link.startswith('http://') or link.startswith('https://')):
        return f"Error: '{link}' doesn't appear to be a valid URL. It should start with http:// or https://"
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO links (user_id, link) VALUES (?, ?)", (user_id, link))
        conn.commit()
        conn.close()
        return f"Link '{link}' saved successfully."
    except sqlite3.Error as e:
        logger.error(f"Database error saving link: {e}")
        return f"Database error: {e}"
    except Exception as e:
        logger.error(f"Error saving link: {e}")
        return f"An error occurred: {e}"

def retrieve_links(user_id: str, keyword: str = None) -> List[str]:
    """Retrieves all saved links for the user."""
    if not user_id:
        return []
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if keyword:
            # Filter links by keyword
            keyword_pattern = f"%{keyword}%"
            cursor.execute(
                "SELECT link FROM links WHERE user_id = ? AND link LIKE ? ORDER BY timestamp DESC", 
                (user_id, keyword_pattern)
            )
        else:
            # Retrieve all links
            cursor.execute("SELECT link FROM links WHERE user_id = ? ORDER BY timestamp DESC", (user_id,))
            
        links = [row['link'] for row in cursor.fetchall()]
        conn.close()
        return links
        
    except sqlite3.Error as e:
        logger.error(f"Database error retrieving links: {e}")
        return []
    except Exception as e:
        logger.error(f"Error retrieving links: {e}")
        return []

def set_reminder(user_id: str, reminder_time_str: str, task: str) -> str:
    """Sets a reminder for the user at a specific time for a given task.
    
    Args:
        user_id: The WhatsApp ID of the user (e.g., 'whatsapp:+1234567890')
        reminder_time_str: A time string like '9:30 PM', 'tomorrow at 10am', 'in 2 hours'
        task: The task to be reminded about
        
    Returns:
        A confirmation message
    """
    global scheduler
    if scheduler is None:
        initialize_scheduler()
    
    if not user_id or not reminder_time_str or not task:
        return "Error: user_id, reminder_time_str, and task are all required."

    # Parse the time string into a datetime object
    reminder_dt = dateparser.parse(reminder_time_str)

    if not reminder_dt:
        return f"Error: I couldn't understand the time '{reminder_time_str}'. Please use a clearer format (e.g., '9:30 PM', 'tomorrow at 10am', 'in 2 hours')."

    # Ensure the time is in the future
    now = datetime.now()
    if reminder_dt <= now:
        # Check if it might be for tomorrow if the time is already past today
        if reminder_dt.time() <= now.time():
            reminder_dt_tomorrow = dateparser.parse(f"tomorrow {reminder_time_str}")
            if reminder_dt_tomorrow and reminder_dt_tomorrow > now:
                reminder_dt = reminder_dt_tomorrow
            else:
                return f"Error: The reminder time '{reminder_time_str}' seems to be in the past."

    try:
        # Save the reminder to the database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO reminders (user_id, task, reminder_time) VALUES (?, ?, ?)",
            (user_id, task, reminder_dt.strftime('%Y-%m-%d %H:%M:%S'))
        )
        reminder_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Create a unique job ID for this reminder
        job_id = f"reminder_{reminder_id}"
        
        # Schedule the reminder
        reminder_text = f"📅 Reminder: {task}"
        scheduler.add_job(
            send_whatsapp_message,
            'date',
            run_date=reminder_dt,
            args=[user_id, reminder_text],
            id=job_id,
            replace_existing=True
        )
        
        # Format the confirmation message
        formatted_time = reminder_dt.strftime('%I:%M %p on %A, %B %d, %Y')
        return f"✅ I'll remind you to '{task}' at {formatted_time}."
    except sqlite3.Error as e:
        logger.error(f"Database error setting reminder: {e}")
        return f"Database error: {e}"
    except Exception as e:
        logger.error(f"Error setting reminder: {e}")
        return f"An error occurred: {e}"

# --- Twilio WhatsApp Function ---

def get_twilio_client() -> Optional[Client]:
    """Get a configured Twilio client from environment variables."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    
    if not account_sid or not auth_token:
        logger.warning("Twilio credentials not properly configured in environment variables")
        return None
    
    return Client(account_sid, auth_token)

def send_whatsapp_message(to_number: str, body: str) -> str:
    """Sends a WhatsApp message using Twilio.
    
    Args:
        to_number: The recipient's phone number, can be with or without the 'whatsapp:' prefix
        body: The message to send
        
    Returns:
        A status message
    """
    client = get_twilio_client()
    if not client:
        error_msg = "Twilio client not configured. Cannot send message."
        logger.error(error_msg)
        return error_msg
    
    # Ensure the number has the 'whatsapp:' prefix
    if not to_number.startswith('whatsapp:'):
        to_number = f'whatsapp:{to_number}'
    
    # Get the WhatsApp sender number from env
    from_number = os.getenv("TWILIO_PHONE_NUMBER")
    if not from_number:
        logger.error("TWILIO_PHONE_NUMBER not set in environment variables")
        return "Error: WhatsApp sender number not configured"
    
    if not from_number.startswith('whatsapp:'):
        from_number = f'whatsapp:{from_number}'
    
    try:
        message = client.messages.create(
            from_=from_number,
            body=body,
            to=to_number
        )
        logger.info(f"Message sent to {to_number}: SID {message.sid}")
        return f"Message sent successfully to {to_number}."
    except Exception as e:
        logger.error(f"Error sending WhatsApp message to {to_number}: {e}")
        return f"Error sending message: {e}"

# --- Reminder Tool ---

# Initialize scheduler
scheduler = None

def initialize_scheduler():
    """Initialize the background scheduler for reminders."""
    global scheduler
    if scheduler is None or not scheduler.running:
        scheduler = BackgroundScheduler(timezone="UTC")
        scheduler.start()
        logger.info("Scheduler initialized and started")
    return scheduler

def cleanup_scheduler():
    """Shutdown the scheduler gracefully."""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler shut down")

# List of all available tools
all_tools = [save_link, retrieve_links, set_reminder] 