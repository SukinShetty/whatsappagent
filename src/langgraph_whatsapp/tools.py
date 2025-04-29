import sqlite3
import os
import logging
import re
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import dateparser
from twilio.rest import Client
from apscheduler.schedulers.background import BackgroundScheduler
from src.langgraph_whatsapp.db import get_db_connection
from src.langgraph_whatsapp.calendar_setup import get_calendar_service
from src.langgraph_whatsapp.sheets_setup import add_expense, check_budget, list_recent_expenses, get_sheets_service, SPREADSHEET_ID, BUDGETS_SHEET, EXPENSES_SHEET
import pytz

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
    """Sets a reminder for the user at a specific time for a given task."""
    global scheduler
    if scheduler is None:
        initialize_scheduler()
    
    if not user_id or not reminder_time_str or not task:
        return "Error: user_id, reminder_time_str, and task are all required."

    # Preprocess the time string to handle more formats
    logger.info(f"Original time string: {reminder_time_str}")
    
    # Handle common time formats like "7pm"
    am_pm_pattern = re.compile(r'(\d+)(?:[\.:](\d+))?\s*(am|pm)', re.IGNORECASE)
    am_pm_match = am_pm_pattern.match(reminder_time_str)
    
    if am_pm_match:
        # We have a time like "7pm" or "7:30pm" or "7.03pm"
        hour = int(am_pm_match.group(1))
        minute = int(am_pm_match.group(2) or 0)  # Default to 0 if no minutes
        am_pm = am_pm_match.group(3).lower()
        
        # Adjust for PM
        if am_pm == 'pm' and hour < 12:
            hour += 12
        # Adjust for AM
        elif am_pm == 'am' and hour == 12:
            hour = 0
            
        # Create datetime for today - FIXED: don't use dateparser for simple times
        now = datetime.now()
        current_year = now.year
        current_month = now.month
        current_day = now.day
        
        reminder_dt = datetime(
            year=current_year,
            month=current_month,
            day=current_day,
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0
        )
        
        # If the time is already past for today, set it for tomorrow
        if reminder_dt <= now:
            reminder_dt = reminder_dt + timedelta(days=1)
            logger.info(f"Time already passed today, setting for tomorrow: {reminder_dt}")
            
        logger.info(f"Parsed time from '{reminder_time_str}': {reminder_dt}")
    
    # Handle 24-hour times without AM/PM
    elif reminder_time_str.replace(":", "").replace(".", "").isdigit():
        # Looks like a 24-hour time without AM/PM
        if "." in reminder_time_str:
            # Convert 18.39 to 18:39
            reminder_time_str = reminder_time_str.replace(".", ":")
        
        # Parse hours and minutes
        if ":" in reminder_time_str:
            hours, minutes = map(int, reminder_time_str.split(":"))
        else:
            # Handle time without colon (e.g., "1830")
            time_str = reminder_time_str.zfill(4)  # Ensure 4 digits
            hours, minutes = int(time_str[:2]), int(time_str[2:])
        
        # Create datetime for today with the specified time
        now = datetime.now()
        reminder_dt = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
        
        # If the time is already past for today, set it for tomorrow
        if reminder_dt <= now:
            reminder_dt = reminder_dt + timedelta(days=1)
            logger.info(f"Time already passed today, setting for tomorrow: {reminder_dt}")
        
        logger.info(f"Created datetime from 24-hour time: {reminder_dt}")
    else:
        # For other time formats, use dateparser
        try:
            now = datetime.now()
            reminder_dt = dateparser.parse(reminder_time_str)
            logger.info(f"Parsed datetime using dateparser: {reminder_dt}")
            
            # Adjust the year/month/day if dateparser set it far in the future
            # This ensures reminders are scheduled for today/tomorrow, not next year
            if reminder_dt and reminder_dt.year > now.year:
                reminder_dt = reminder_dt.replace(year=now.year, month=now.month, day=now.day)
                logger.info(f"Adjusted future date to current date: {reminder_dt}")
                
                # If time already passed for today, set it for tomorrow
                if reminder_dt <= now:
                    reminder_dt = reminder_dt + timedelta(days=1)
                    logger.info(f"Time already passed today, adjusted to tomorrow: {reminder_dt}")
        except Exception as e:
            logger.error(f"Error parsing time '{reminder_time_str}': {e}")
            return f"Error: I couldn't understand the time '{reminder_time_str}'. Please use a format like '3pm', '15:00', or 'tomorrow at 10am'."

    if not reminder_dt:
        return f"Error: I couldn't understand the time '{reminder_time_str}'. Please use a clearer format (e.g., '9:30 PM', 'tomorrow at 10am', 'in 2 hours')."

    # Ensure the time is in the future
    now = datetime.now()
    if reminder_dt <= now:
        # Check if it might be for tomorrow if the time is already past today
        if reminder_dt.time() <= now.time():
            reminder_dt_tomorrow = reminder_dt + timedelta(days=1)
            reminder_dt = reminder_dt_tomorrow
            logger.info(f"Adjusted to tomorrow: {reminder_dt}")
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
        logger.info(f"Scheduling reminder for: {reminder_dt}")
        
        # Force the year to be current year (not 2025)
        current_year = datetime.now().year
        if reminder_dt.year != current_year:
            logger.warning(f"Fixing incorrect year {reminder_dt.year} to current year {current_year}")
            reminder_dt = reminder_dt.replace(year=current_year)
            logger.info(f"Updated reminder datetime: {reminder_dt}")
        
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
    """Sends a WhatsApp message using Twilio."""
    # Print to console for immediate visibility
    print(f"\n\n!!! REMINDER ALERT !!!\nTO: {to_number}\nMESSAGE: {body}\n")
    
    client = get_twilio_client()
    if not client:
        error_msg = "Twilio client not configured. Cannot send message."
        logger.error(error_msg)
        # For testing, log the message we would have sent
        logger.info(f"WOULD HAVE SENT to {to_number}: {body}")
        return error_msg
    
    # Ensure the number has the 'whatsapp:' prefix
    if not to_number.startswith('whatsapp:'):
        to_number = f'whatsapp:{to_number}'
    
    # Get the WhatsApp sender number from env
    from_number = os.getenv("TWILIO_PHONE_NUMBER")
    if not from_number:
        logger.error("TWILIO_PHONE_NUMBER not set in environment variables")
        from_number = "whatsapp:+14155238886"  # Default to sandbox number
        logger.info(f"Using default WhatsApp sender: {from_number}")
    
    if not from_number.startswith('whatsapp:'):
        from_number = f'whatsapp:{from_number}'
    
    try:
        logger.info(f"Sending WhatsApp message to {to_number}: {body}")
        logger.info(f"From number: {from_number}")
        
        message = client.messages.create(
            from_=from_number,
            body=body,
            to=to_number
        )
        logger.info(f"Message sent to {to_number}: SID {message.sid}")
        return f"Message sent successfully to {to_number}."
    except Exception as e:
        logger.error(f"Error sending WhatsApp message to {to_number}: {e}")
        # For debugging purposes, log what we tried to send
        logger.info(f"Failed to send message to {to_number} from {from_number}: {body}")
        return f"Error sending message: {e}"

# --- Reminder Tool ---

# Initialize scheduler at module level
scheduler = None

def initialize_scheduler():
    """Initialize the background scheduler for reminders."""
    global scheduler
    if scheduler is None or not scheduler.running:
        try:
            logger.info("Initializing scheduler for reminders...")
            # Set misfire_grace_time to 1 second and check every 1 second for better responsiveness
            scheduler = BackgroundScheduler(
                timezone="UTC",
                job_defaults={
                    'misfire_grace_time': 1
                }
            )
            scheduler.start()
            logger.info("Scheduler initialized and started successfully")
            
            # Load existing reminders from database and reschedule them
            _load_existing_reminders()
            
            return scheduler
        except Exception as e:
            logger.error(f"Error initializing scheduler: {e}")
            return None
    return scheduler

def _load_existing_reminders():
    """Load existing reminders from the database and schedule them."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, task, reminder_time 
            FROM reminders 
            WHERE completed = 0 AND reminder_time > datetime('now')
            ORDER BY reminder_time ASC
        """)
        reminders = cursor.fetchall()
        conn.close()
        
        if reminders:
            logger.info(f"Found {len(reminders)} existing reminders to reschedule")
            for reminder in reminders:
                reminder_id = reminder['id']
                user_id = reminder['user_id']
                task = reminder['task']
                reminder_time = reminder['reminder_time']
                
                # Parse the reminder time
                reminder_dt = dateparser.parse(reminder_time)
                
                if reminder_dt:
                    # Fix year if needed
                    current_year = datetime.now().year
                    if reminder_dt.year != current_year:
                        logger.warning(f"Fixing incorrect year {reminder_dt.year} to current year {current_year}")
                        reminder_dt = reminder_dt.replace(year=current_year)
                        logger.info(f"Updated reminder datetime: {reminder_dt}")
                    
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
                    logger.info(f"Rescheduled reminder [{reminder_id}] for {user_id} at {reminder_time}")
        else:
            logger.info("No existing reminders to reschedule")
    except Exception as e:
        logger.error(f"Error loading existing reminders: {e}")

def cleanup_scheduler():
    """Shutdown the scheduler gracefully."""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler shut down")

# Add this new function just before the "# List of all available tools" line
def book_calendar_event(user_id: str, title: str, date_str: str, time_str: str, duration_minutes: int = 60) -> str:
    """Books an event on Google Calendar.
    
    Args:
        user_id: The WhatsApp ID of the user
        title: The title/summary of the event
        date_str: The date of the event (e.g., "May 1", "tomorrow", "next Monday")
        time_str: The time of the event (e.g., "3:00 PM", "15:00")
        duration_minutes: Duration of the event in minutes (default: 60)
        
    Returns:
        A confirmation message
    """
    logger.info(f"Booking calendar event: {title} on {date_str} at {time_str} for {duration_minutes} minutes")
    
    # Get the calendar service
    service = get_calendar_service()
    if not service:
        return "Error: Could not connect to Google Calendar. Please check your credentials."
    
    try:
        # Parse the date and time
        date_time_str = f"{date_str} {time_str}"
        logger.info(f"Parsing date and time: {date_time_str}")
        
        # Try to parse the date and time string
        start_time = dateparser.parse(date_time_str)
        if not start_time:
            return f"Error: Could not understand the date and time '{date_time_str}'. Please use a clearer format."
        
        # If the year is far in the future, set it to the current year
        current_year = datetime.now().year
        if start_time.year > current_year + 1:
            start_time = start_time.replace(year=current_year)
        
        # Set end time
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        # Format times for Google Calendar API
        start_time_str = start_time.isoformat()
        end_time_str = end_time.isoformat()
        
        # Create the event
        event = {
            'summary': title,
            'description': f'Event booked by WhatsApp agent for {user_id}',
            'start': {
                'dateTime': start_time_str,
                'timeZone': 'Asia/Kolkata',  # You can change this to your timezone
            },
            'end': {
                'dateTime': end_time_str,
                'timeZone': 'Asia/Kolkata',  # You can change this to your timezone
            },
            'reminders': {
                'useDefault': True,
            },
        }
        
        # Add the event to the calendar
        event = service.events().insert(calendarId='primary', body=event).execute()
        event_link = event.get('htmlLink', '')
        
        # Format response with event details
        formatted_start = start_time.strftime('%I:%M %p on %A, %B %d, %Y')
        return f"✅ Successfully booked: '{title}' at {formatted_start} for {duration_minutes} minutes."
    
    except Exception as e:
        logger.error(f"Error booking calendar event: {e}")
        return f"An error occurred while booking the event: {e}"

def track_expense(user_id: str, amount: str, category: str) -> str:
    """Track a new expense in the finance spreadsheet.
    
    Args:
        user_id: The WhatsApp ID of the user
        amount: The amount spent (e.g., "500", "1000.50")
        category: The expense category (e.g., "groceries", "food", "entertainment")
        
    Returns:
        A confirmation message
    """
    logger.info(f"Tracking expense: {amount} for {category}")
    
    try:
        # Convert amount to a number
        amount_float = float(amount.replace('$', '').replace(',', ''))
        
        # Add the expense to Google Sheets
        result = add_expense(amount_float, category)
        return result
    except ValueError:
        return f"Invalid amount format: {amount}. Please provide a valid number."
    except Exception as e:
        logger.error(f"Error tracking expense: {e}")
        return f"An error occurred while tracking the expense: {e}"

def get_budget_status(user_id: str, category: str) -> str:
    """Get the budget status for a specific category.
    
    Args:
        user_id: The WhatsApp ID of the user
        category: The budget category to check (e.g., "groceries", "food", "entertainment")
        
    Returns:
        A message with budget information
    """
    logger.info(f"Checking budget for category: {category}")
    
    try:
        # Get budget status from Google Sheets
        result = check_budget(category)
        return result
    except Exception as e:
        logger.error(f"Error checking budget: {e}")
        return f"An error occurred while checking your budget: {e}"

def get_recent_expenses(user_id: str, limit: int = 5) -> str:
    """Get a list of recent expenses.
    
    Args:
        user_id: The WhatsApp ID of the user
        limit: The maximum number of expenses to return (default: 5)
        
    Returns:
        A formatted list of recent expenses
    """
    logger.info(f"Getting {limit} recent expenses")
    
    try:
        # Get recent expenses from Google Sheets
        result = list_recent_expenses(limit)
        return result
    except Exception as e:
        logger.error(f"Error getting recent expenses: {e}")
        return f"An error occurred while retrieving your expenses: {e}"

def get_consolidated_budget_report(user_id: str) -> str:
    """Get a consolidated report of all category budgets.
    
    Args:
        user_id: The WhatsApp ID of the user
        
    Returns:
        A consolidated budget report with totals
    """
    logger.info(f"Generating consolidated budget report for user: {user_id}")
    
    try:
        # Get sheets service
        service = get_sheets_service()
        if not service:
            return "Could not connect to Google Sheets. Please check your credentials."
        
        # Get current month
        current_month = datetime.now().strftime('%Y-%m')
        
        # Get all budgets
        budget_result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f'{BUDGETS_SHEET}!A1:B100'
        ).execute()
        
        budget_rows = budget_result.get('values', [])
        if not budget_rows or len(budget_rows) <= 1:
            return "No budget data found."
        
        # Get all expenses
        expense_result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f'{EXPENSES_SHEET}!A1:C100'
        ).execute()
        
        expense_rows = expense_result.get('values', [])
        if not expense_rows or len(expense_rows) <= 1:
            # No expenses yet, just report budgets
            categories = []
            total_budget = 0
            
            # Get top budget categories
            for row in budget_rows[1:]:  # Skip header
                if len(row) >= 2:
                    try:
                        category_name = row[0]
                        budget_amount = float(row[1])
                        total_budget += budget_amount
                        
                        # Add only main categories, avoiding duplicates
                        if not any(cat == category_name for cat, _, _ in categories):
                            categories.append((category_name, budget_amount, 0))
                    except ValueError:
                        continue
            
            # Format the response
            response = "💰 Budget Summary 💰\n\n"
            
            # Filter to keep only top-level categories
            main_categories = []
            main_category_names = set()
            
            for cat, budget, spent in categories:
                # Skip if this appears to be a subcategory of one we already have
                cat_base = cat.split()[0].lower()
                if cat_base in main_category_names:
                    continue
                
                main_category_names.add(cat_base)
                main_categories.append((cat, budget, spent))
            
            # Sort by budget amount (highest first)
            main_categories.sort(key=lambda x: x[1], reverse=True)
            
            # Format each category
            for category_name, budget_amount, spent in main_categories[:5]:  # Top 5 categories
                remaining = budget_amount - spent
                response += f"{category_name}:\n  Budget: {budget_amount:.0f}\n  Spent: {spent:.0f}\n  Remaining: {budget_amount:.0f} ✅\n\n"
            
            # Add total
            response += f"Total Budget: {total_budget:.0f}\nTotal Spent: 0\nTotal Remaining: {total_budget:.0f} ✅"
            
            return response
            
        # Calculate spent amounts by category
        category_spent = {}
        total_spent = 0
        
        for row in expense_rows[1:]:  # Skip header
            if len(row) >= 3:
                expense_date = row[0]
                try:
                    expense_amount = float(row[1])
                    expense_category = row[2]
                    
                    # Check if expense is from current month
                    if expense_date.startswith(current_month):
                        total_spent += expense_amount
                        
                        # Add to category total
                        if expense_category in category_spent:
                            category_spent[expense_category] += expense_amount
                        else:
                            category_spent[expense_category] = expense_amount
                except (ValueError, IndexError):
                    continue
        
        # Combine budget and spent data
        categories = []
        total_budget = 0
        
        for row in budget_rows[1:]:  # Skip header
            if len(row) >= 2:
                try:
                    category_name = row[0]
                    budget_amount = float(row[1])
                    total_budget += budget_amount
                    
                    # Get spent amount for this category (with fuzzy matching)
                    spent = 0
                    for expense_cat, expense_amount in category_spent.items():
                        if (category_name.lower() == expense_cat.lower() or
                            category_name.lower() in expense_cat.lower() or
                            expense_cat.lower() in category_name.lower()):
                            spent += expense_amount
                    
                    # Add to categories list
                    if not any(cat == category_name for cat, _, _ in categories):
                        categories.append((category_name, budget_amount, spent))
                except ValueError:
                    continue
        
        # Format the response
        response = "💰 Budget Summary 💰\n\n"
        
        # Filter to keep only top-level categories
        main_categories = []
        main_category_names = set()
        
        for cat, budget, spent in categories:
            # Skip if this appears to be a subcategory of one we already have
            cat_base = cat.split()[0].lower()
            if cat_base in main_category_names:
                continue
            
            main_category_names.add(cat_base)
            main_categories.append((cat, budget, spent))
        
        # Sort by budget amount (highest first)
        main_categories.sort(key=lambda x: x[1], reverse=True)
        
        # Format each category
        for category_name, budget_amount, spent in main_categories[:5]:  # Top 5 categories
            remaining = budget_amount - spent
            status = "✅" if remaining >= 0 else "❌"
            response += f"{category_name}:\n  Budget: {budget_amount:.0f}\n  Spent: {spent:.0f}\n  Remaining: {remaining:.0f} {status}\n\n"
        
        # Add total
        total_remaining = total_budget - total_spent
        total_status = "✅" if total_remaining >= 0 else "❌"
        response += f"Total Budget: {total_budget:.0f}\nTotal Spent: {total_spent:.0f}\nTotal Remaining: {total_remaining:.0f} {total_status}"
        
        return response
        
    except Exception as e:
        logger.error(f"Error generating consolidated budget report: {e}")
        return f"An error occurred while generating the consolidated budget report: {e}"

# List of all available tools
all_tools = [save_link, retrieve_links, set_reminder, book_calendar_event, track_expense, get_budget_status, get_recent_expenses, get_consolidated_budget_report] 