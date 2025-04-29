import logging
import json
import uuid
import re
from datetime import datetime, timedelta
from src.langgraph_whatsapp.tools import extract_links, save_link, retrieve_links, set_reminder, book_calendar_event, track_expense, get_budget_status, get_recent_expenses, get_consolidated_budget_report
from src.langgraph_whatsapp.db import get_db_connection

LOGGER = logging.getLogger(__name__)


class Agent:
    def __init__(self):
        try:
            # Initialize any required setup
            pass
        except Exception as e:
            LOGGER.error(f"Error initializing agent: {e}")
            raise

    async def invoke(self, id: str, user_message: str, images: list = None) -> dict:
        """Process a user message and return a response."""
        try:
            # Extract any links from the message
            links = extract_links(user_message)
            msg_lower = user_message.lower()
            
            # Fix typo in "remind" that appears as "remnind" or "rmeind"
            if "remnind" in msg_lower:
                msg_lower = msg_lower.replace("remnind", "remind")
                user_message = user_message.replace("remnind", "remind")
            elif "rmeind" in msg_lower:
                msg_lower = msg_lower.replace("rmeind", "remind")
                user_message = user_message.replace("rmeind", "remind")
                LOGGER.info(f"Corrected 'rmeind' to 'remind': {user_message}")
            
            # FINANCE FEATURES: Check for expense tracking requests
            # Pattern: "I spent [amount] on [category]"
            expense_patterns = [
                r"(?:i|we)\s+(?:have\s+)?(?:spent|paid|bought)\s+(?:\$)?(\d+(?:\.\d+)?)\s+(?:on|for)\s+([a-zA-Z\s]+)",
                r"(?:i|we)\s+(?:have\s+)?(?:spent|paid|bought)\s+(?:on|for)\s+([a-zA-Z\s]+)\s+(?:\$)?(\d+(?:\.\d+)?)",
                r"(?:track|add|record)\s+(?:expense|transaction|purchase)\s+(?:of\s+)?(?:\$)?(\d+(?:\.\d+)?)\s+(?:on|for)\s+([a-zA-Z\s]+)",
                r"(?:\$)?(\d+(?:\.\d+)?)\s+(?:spent|paid)\s+(?:on|for)\s+([a-zA-Z\s]+)",
                r"(?:i|we)\s+(?:used|put|invested)\s+(?:\$)?(\d+(?:\.\d+)?)\s+(?:on|for|in)\s+([a-zA-Z\s]+)",
                # Very generic pattern as fallback - finds any number followed by "on" or "for" and a category
                r"(\d+(?:\.\d+)?).+(?:on|for)\s+([a-zA-Z\s]+)"
            ]
            
            # Check if the message contains multiple lines with expenses
            if "\n" in user_message and "spent" in msg_lower:
                lines = user_message.split("\n")
                all_results = []
                
                for line in lines:
                    if not line.strip():
                        continue
                        
                    line_lower = line.lower()
                    if "spent" in line_lower:
                        # Try to extract amount and category
                        extracted = False
                        
                        for pattern in expense_patterns:
                            expense_match = re.search(pattern, line_lower)
                            if expense_match:
                                try:
                                    # Get amount and category based on the pattern
                                    if "on" in expense_match.group(0) and "for" not in expense_match.group(0):
                                        # Pattern with "on"
                                        if "spent" in expense_match.group(0) or "paid" in expense_match.group(0) or "bought" in expense_match.group(0):
                                            amount = expense_match.group(1)
                                            category = expense_match.group(2).strip()
                                        else:
                                            # Handle reverse patterns
                                            groups = expense_match.groups()
                                            if len(groups) == 2:
                                                try:
                                                    float(groups[0])  # Try to convert first group to float
                                                    amount = groups[0]
                                                    category = groups[1].strip()
                                                except ValueError:
                                                    # If first group is not a number, it's probably the category
                                                    amount = groups[1]
                                                    category = groups[0].strip()
                                    else:
                                        # Other patterns
                                        groups = expense_match.groups()
                                        if len(groups) == 2:
                                            try:
                                                float(groups[0])  # Try to convert first group to float
                                                amount = groups[0]
                                                category = groups[1].strip()
                                            except ValueError:
                                                # If first group is not a number, it's probably the category
                                                amount = groups[1]
                                                category = groups[0].strip()
                                            
                                    LOGGER.info(f"Extracted expense from line - Amount: {amount}, Category: {category}")
                                    
                                    # Track the expense
                                    result = track_expense(id, amount, category)
                                    all_results.append(result)
                                    extracted = True
                                    break
                                except Exception as e:
                                    LOGGER.error(f"Error tracking expense from line: {e}")
                                    
                        if not extracted and "spent" in line_lower and re.search(r'\d+', line_lower):
                            # Direct extraction as fallback
                            amount_match = re.search(r'(\d+(?:\.\d+)?)', line_lower)
                            if amount_match:
                                amount = amount_match.group(1)
                                
                                # Try to find the category after "on" or "for"
                                category_match = re.search(r'(?:on|for)\s+([a-zA-Z\s]+)(?:$|\.)', line_lower)
                                if category_match:
                                    category = category_match.group(1).strip()
                                    LOGGER.info(f"Direct extraction from line - Amount: {amount}, Category: {category}")
                                    
                                    # Track the expense
                                    result = track_expense(id, amount, category)
                                    all_results.append(result)
                
                # Return all tracked expenses
                if all_results:
                    return {
                        "response": "\n".join(all_results),
                        "error": None
                    }
            
            # If not a multi-line message, proceed with single expense tracking
            expense_found = False
            for pattern in expense_patterns:
                expense_match = re.search(pattern, msg_lower)
                if expense_match:
                    try:
                        # Get amount and category based on the pattern
                        if "on" in expense_match.group(0) and "for" not in expense_match.group(0):
                            # Pattern with "on"
                            if "spent" in expense_match.group(0) or "paid" in expense_match.group(0) or "bought" in expense_match.group(0):
                                amount = expense_match.group(1)
                                category = expense_match.group(2).strip()
                            else:
                                # Handle reverse patterns
                                groups = expense_match.groups()
                                if len(groups) == 2:
                                    try:
                                        float(groups[0])  # Try to convert first group to float
                                        amount = groups[0]
                                        category = groups[1].strip()
                                    except ValueError:
                                        # If first group is not a number, it's probably the category
                                        amount = groups[1]
                                        category = groups[0].strip()
                        else:
                            # Other patterns
                            groups = expense_match.groups()
                            if len(groups) == 2:
                                try:
                                    float(groups[0])  # Try to convert first group to float
                                    amount = groups[0]
                                    category = groups[1].strip()
                                except ValueError:
                                    # If first group is not a number, it's probably the category
                                    amount = groups[1]
                                    category = groups[0].strip()
                            
                        LOGGER.info(f"Extracted expense - Amount: {amount}, Category: {category}")
                        
                        # Track the expense
                        result = track_expense(id, amount, category)
                        expense_found = True
                        return {
                            "response": result,
                            "error": None
                        }
                    except Exception as e:
                        LOGGER.error(f"Error tracking expense: {e}")
                        return {
                            "response": "Sorry, I couldn't track that expense. Please try using a format like: 'I spent 500 on groceries'.",
                            "error": str(e)
                        }
            
            # Also add a direct check for the word "spent" in the message with number extraction
            if not expense_found and "spent" in msg_lower and re.search(r'\d+', msg_lower):
                # Try to extract amount and category more directly
                amount_match = re.search(r'(\d+(?:\.\d+)?)', msg_lower)
                if amount_match:
                    amount = amount_match.group(1)
                    
                    # Try to find the category after "on" or "for"
                    category_match = re.search(r'(?:on|for)\s+([a-zA-Z\s]+)(?:$|\.)', msg_lower)
                    if category_match:
                        category = category_match.group(1).strip()
                        LOGGER.info(f"Direct extraction - Amount: {amount}, Category: {category}")
                        
                        # Track the expense
                        result = track_expense(id, amount, category)
                        return {
                            "response": result,
                            "error": None
                        }
            
            # Check for budget status requests
            # Pattern: "What's my budget for [category]?"
            budget_patterns = [
                r"(?:what(?:'s|s|\sis)?\s+my|check|show)\s+(?:budget|spending|limit)\s+(?:for|on)?\s+([a-zA-Z\s]+)",
                r"how\s+much\s+(?:can\s+i\s+spend|do\s+i\s+have\s+left)\s+(?:on|for)\s+([a-zA-Z\s]+)",
                r"budget\s+(?:for|on)\s+([a-zA-Z\s]+)"
            ]
            
            # Check for multiple budget queries in one message
            if "\n" in user_message and "budget" in msg_lower:
                lines = user_message.split("\n")
                all_results = []
                all_categories_found = False
                
                for line in lines:
                    if not line.strip():
                        continue
                        
                    line_lower = line.lower()
                    if "budget" in line_lower:
                        # Try to extract category
                        category_found = False
                        
                        for pattern in budget_patterns:
                            budget_match = re.search(pattern, line_lower)
                            if budget_match:
                                try:
                                    category = budget_match.group(1).strip()
                                    LOGGER.info(f"Checking budget for category: {category}")
                                    
                                    # Get budget status
                                    result = get_budget_status(id, category)
                                    all_results.append(result)
                                    category_found = True
                                    break
                                except Exception as e:
                                    LOGGER.error(f"Error checking budget: {e}")
                                    all_results.append(f"Sorry, I couldn't check the budget for that category.")
                        
                        # If no category found but the line asks for budget
                        if not category_found and ("what" in line_lower or "show" in line_lower or "check" in line_lower) and "budget" in line_lower:
                            # Might be asking for all budgets together
                            all_categories_found = True
                
                # If multiple budget lines were found or we detected a query for all budgets
                if all_results:
                    # If asking for all categories or multiple categories detected
                    if all_categories_found or len(all_results) > 2:
                        try:
                            # Return consolidated budget report instead of individual results
                            consolidated_budget = get_consolidated_budget_report(id)
                            return {
                                "response": consolidated_budget,
                                "error": None
                            }
                        except Exception as e:
                            LOGGER.error(f"Error getting consolidated budget: {e}")
                    
                    return {
                        "response": "\n\n".join(all_results),
                        "error": None
                    }
            
            # Original single budget query handling
            for pattern in budget_patterns:
                budget_match = re.search(pattern, msg_lower)
                if budget_match:
                    try:
                        category = budget_match.group(1).strip()
                        LOGGER.info(f"Checking budget for category: {category}")
                        
                        # Get budget status
                        result = get_budget_status(id, category)
                        return {
                            "response": result,
                            "error": None
                        }
                    except Exception as e:
                        LOGGER.error(f"Error checking budget: {e}")
                        return {
                            "response": "Sorry, I couldn't check that budget. Please try using a format like: 'What's my budget for groceries?'",
                            "error": str(e)
                        }
            
            # New handler for "this is the budget" or "show budget" messages
            # Check for direct budget statement (like what was shown in the screenshot)
            if "budget" in msg_lower and (msg_lower.startswith("this is") or msg_lower.startswith("here is") or "show" in msg_lower or "list" in msg_lower):
                try:
                    LOGGER.info("User requested to see all budgets")
                    # Return all budget categories
                    all_budgets = get_budget_status(id, "all")
                    return {
                        "response": all_budgets,
                        "error": None
                    }
                except Exception as e:
                    LOGGER.error(f"Error showing all budgets: {e}")
                    return {
                        "response": "Sorry, I couldn't retrieve your budget information.",
                        "error": str(e)
                    }
                    
            # Even more direct handler for the exact message in the screenshot
            if msg_lower == "this is the budget":
                try:
                    LOGGER.info("User sent exact 'this is the budget' message")
                    # Return all budget categories
                    all_budgets = get_budget_status(id, "all")
                    return {
                        "response": all_budgets,
                        "error": None
                    }
                except Exception as e:
                    LOGGER.error(f"Error showing all budgets: {e}")
                    return {
                        "response": "Sorry, I couldn't retrieve your budget information.",
                        "error": str(e)
                    }
            
            # Handler for "show all budgets" or "budget summary" type requests
            if any(phrase in msg_lower for phrase in ["all budget", "budget summary", "total budget", "overall budget"]):
                try:
                    LOGGER.info("User requested consolidated budget report")
                    consolidated_budget = get_consolidated_budget_report(id)
                    return {
                        "response": consolidated_budget,
                        "error": None
                    }
                except Exception as e:
                    LOGGER.error(f"Error generating consolidated budget report: {e}")
                    return {
                        "response": "Sorry, I couldn't generate your budget summary.",
                        "error": str(e)
                    }
            
            # Check for recent expenses requests
            # Pattern: "Show my last [number] expenses"
            expense_history_keywords = ["expense", "expenses", "spent", "spending", "transactions", "purchases", "costs", "payments"]
            view_keywords = ["show", "list", "recent", "last", "history", "view", "see", "get", "what are"]
            
            if any(keyword in msg_lower for keyword in expense_history_keywords) and any(keyword in msg_lower for keyword in view_keywords):
                try:
                    # Extract number of expenses to show
                    limit_match = re.search(r"(?:last|recent)\s+(\d+)", msg_lower)
                    limit = int(limit_match.group(1)) if limit_match else 5
                    
                    LOGGER.info(f"Listing {limit} recent expenses")
                    
                    # Get recent expenses
                    result = get_recent_expenses(id, limit)
                    return {
                        "response": result,
                        "error": None
                    }
                except Exception as e:
                    LOGGER.error(f"Error listing expenses: {e}")
                    return {
                        "response": "Sorry, I couldn't list your expenses. Please try using a format like: 'Show my last 5 expenses'.",
                        "error": str(e)
                    }
            
            # FIRST PRIORITY: Check for calendar booking requests
            if ("book" in msg_lower or "schedule" in msg_lower or "create" in msg_lower) and ("meeting" in msg_lower or "event" in msg_lower or "appointment" in msg_lower):
                try:
                    LOGGER.info(f"Processing calendar booking request: {user_message}")
                    
                    # Extract meeting details using regex patterns
                    
                    # 1. Extract meeting title/description
                    title_patterns = [
                        r"(?:book|schedule|create)\s+(?:a\s+)?(?:meeting|event|appointment)\s+with\s+([^\d\n]+?)(?:\s+on|\s+at|$)",
                        r"meeting\s+with\s+([^\d\n]+?)(?:\s+on|\s+at|$)",
                        r"(?:book|schedule|create)\s+(?:a\s+)?([^\d\n]+?)(?:\s+on|\s+at|$)"
                    ]
                    
                    title = None
                    for pattern in title_patterns:
                        title_match = re.search(pattern, user_message, re.IGNORECASE)
                        if title_match:
                            title = title_match.group(1).strip()
                            if not title.lower().startswith("meeting with"):
                                title = f"Meeting with {title}"
                            break
                    
                    if not title:
                        title = "Meeting"  # Default title
                    
                    # 2. Extract date
                    date_pattern = r"(?:on|for)\s+([a-zA-Z]+\s+\d+(?:st|nd|rd|th)?|tomorrow|today|next\s+[a-zA-Z]+|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)"
                    date_match = re.search(date_pattern, user_message, re.IGNORECASE)
                    
                    date_str = None
                    if date_match:
                        date_str = date_match.group(1).strip()
                    else:
                        # If no explicit date, check if there's a day of week mentioned
                        day_pattern = r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b"
                        day_match = re.search(day_pattern, msg_lower, re.IGNORECASE)
                        if day_match:
                            date_str = day_match.group(1).strip()
                        else:
                            # Default to tomorrow if no date specified
                            date_str = "tomorrow"
                    
                    # 3. Extract time
                    time_pattern = r"at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?|\d{1,2}(?::\d{2})?)"
                    time_match = re.search(time_pattern, user_message, re.IGNORECASE)
                    
                    time_str = None
                    if time_match:
                        time_str = time_match.group(1).strip()
                    else:
                        # Default to 9:00 AM if no time specified
                        time_str = "9:00 AM"
                    
                    # 4. Extract duration (optional)
                    duration_pattern = r"for\s+(\d+)\s*(?:min|minutes|hour|hours)?"
                    duration_match = re.search(duration_pattern, user_message, re.IGNORECASE)
                    
                    duration_minutes = 60  # Default duration: 1 hour
                    if duration_match:
                        duration_val = int(duration_match.group(1))
                        if "hour" in user_message[duration_match.start():duration_match.end()]:
                            duration_minutes = duration_val * 60
                        else:
                            duration_minutes = duration_val
                    
                    LOGGER.info(f"Extracted event details - Title: '{title}', Date: '{date_str}', Time: '{time_str}', Duration: {duration_minutes} minutes")
                    
                    # Book the event
                    result = book_calendar_event(id, title, date_str, time_str, duration_minutes)
                    return {
                        "response": result,
                        "error": None
                    }
                except Exception as e:
                    LOGGER.error(f"Error booking calendar event: {e}")
                    return {
                        "response": "Sorry, I couldn't book that event. Please try using a format like: 'Book a meeting with Akhil on May 1st at 3 PM'.",
                        "error": str(e)
                    }
            
            # SECOND PRIORITY: Check for reminder requests
            if "remind" in msg_lower:
                try:
                    # Check multiple reminder patterns
                    LOGGER.info(f"Processing reminder request: {user_message}")
                    
                    # Pattern 1: "remind me to X at Y"
                    if " at " in user_message:
                        msg_parts = user_message.split(" at ")
                        task = msg_parts[0].replace("remind me to ", "").replace("remind me ", "").strip()
                        time_str = msg_parts[1].strip()
                        
                        # If we got a time that looks like "18.39 ist", convert to standard format
                        if "ist" in time_str.lower():
                            time_str = time_str.lower().replace("ist", "").strip()
                        if "." in time_str:
                            time_str = time_str.replace(".", ":")
                        
                        LOGGER.info(f"Extracted task: '{task}', time: '{time_str}'")
                        
                        result = set_reminder(id, time_str, task)
                        return {
                            "response": result,
                            "error": None
                        }
                    # Pattern 2: "remind me in X to Y"
                    elif " in " in user_message and " to " in user_message:
                        time_part = user_message.split(" to ")[0]
                        time_str = time_part.split(" in ")[1].strip()
                        task = user_message.split(" to ")[1].strip()
                    # Pattern 3: "remind me tomorrow to X"
                    elif "tomorrow" in user_message and " to " in user_message:
                        time_str = "tomorrow"
                        task = user_message.split(" to ")[1].strip()
                    # Pattern 4: "remind me at X to Y"
                    elif " at " in user_message and " to " in user_message:
                        parts = user_message.split(" to ")
                        task = parts[1].strip()
                        time_str = parts[0].split(" at ")[1].strip()
                    else:
                        # Try to find time patterns
                        time_match = re.search(r'(tomorrow|today|in \d+ (hour|minute|day)s?|at \d+(\:\d+)?\s*(am|pm)|morning|afternoon|evening)', msg_lower)
                        time_str = time_match.group(0) if time_match else "tomorrow"
                        
                        # Extract everything after "to" or "about" as the task
                        task_match = re.search(r'(to|about)\s+(.+)', msg_lower)
                        task = task_match.group(2) if task_match else "your task"
                    
                    LOGGER.info(f"Extracted time: '{time_str}', task: '{task}'")
                    
                    # Call the set_reminder function
                    result = set_reminder(id, time_str, task)
                    return {
                        "response": result,
                        "error": None
                    }
                    
                except Exception as e:
                    LOGGER.error(f"Error setting reminder: {e}")
                    return {
                        "response": "Sorry, I couldn't set that reminder. Please try using a format like: 'remind me to call John at 3pm' or 'remind me tomorrow to check email'.",
                        "error": str(e)
                    }
            
            # THIRD PRIORITY: Handle saving new links if present in message
            if links:
                # Save each link found in the message
                for link in links:
                    try:
                        save_link(id, link)
                        return {
                            "response": f"I've saved the link: {link}",
                            "error": None
                        }
                    except Exception as e:
                        LOGGER.error(f"Error saving link: {e}")
                        return {
                            "response": "Sorry, I couldn't save that link. Please try again.",
                            "error": str(e)
                        }
            
            # Check if the message is asking for reminders
            if any(word in msg_lower for word in ["reminder", "reminders"]) and any(word in msg_lower for word in ["show", "get", "my", "list", "see"]):
                try:
                    # Get reminders from database
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT task, reminder_time FROM reminders 
                        WHERE user_id = ? AND completed = 0
                        ORDER BY reminder_time ASC
                    """, (id,))
                    reminders = cursor.fetchall()
                    conn.close()
                    
                    if reminders:
                        reminder_text = "\n".join([f"- {row['task']} at {row['reminder_time']}" for row in reminders])
                        return {
                            "response": f"Here are your upcoming reminders:\n{reminder_text}",
                            "error": None
                        }
                    else:
                        return {
                            "response": "You don't have any upcoming reminders.",
                            "error": None
                        }
                except Exception as e:
                    LOGGER.error(f"Error retrieving reminders: {e}")
                    return {
                        "response": "Sorry, I couldn't retrieve your reminders. Please try again.",
                        "error": str(e)
                    }
            
            # FOURTH PRIORITY: Check if the message is asking for saved links
            if any(keyword in msg_lower for keyword in ["show", "get", "my", "share", "find"]) and any(keyword in msg_lower for keyword in ["link", "links", "repo", "repository"]):
                try:
                    # Get all links first
                    all_links = retrieve_links(id)
                    
                    # Filter links based on keywords in the user's message
                    filtered_links = all_links
                    
                    # Check for specific entities mentioned in the request
                    if "elon" in msg_lower and ("musk" in msg_lower or "tweet" in msg_lower):
                        filtered_links = [link for link in all_links if ("x.com/elonmusk" in link.lower() or "twitter.com/elonmusk" in link.lower())]
                    # Filter for specific types of links
                    elif "x.com" in msg_lower or "twitter" in msg_lower:
                        filtered_links = [link for link in all_links if "x.com" in link.lower() or "twitter.com" in link.lower()]
                    elif "github" in msg_lower:
                        filtered_links = [link for link in all_links if "github.com" in link.lower()]
                    elif "skyreels" in msg_lower or "skyreel" in msg_lower:
                        filtered_links = [link for link in all_links if "skyreels" in link.lower()]
                    elif "ashpreet" in msg_lower:
                        filtered_links = [link for link in all_links if "ashpreet" in link.lower()]
                    elif "linkedin" in msg_lower:
                        filtered_links = [link for link in all_links if "linkedin.com" in link.lower()]
                    
                    if filtered_links:
                        links_text = "\n".join([f"- {link}" for link in filtered_links])
                        return {
                            "response": f"Here are your saved links:\n{links_text}",
                            "error": None
                        }
                    else:
                        return {
                            "response": "You don't have any saved links that match your request.",
                            "error": None
                        }
                except Exception as e:
                    LOGGER.error(f"Error retrieving links: {e}")
                    return {
                        "response": "Sorry, I couldn't retrieve your links. Please try again.",
                        "error": str(e)
                    }
            
            # Default response if no specific action was taken
            return {
                "response": "I'm not sure what you want me to do. You can ask me to:\n1. Save links\n2. Show your saved links\n3. Set reminders\n4. Book calendar events\n5. Track expenses (e.g., 'I spent 500 on groceries')\n6. Check budgets (e.g., 'What's my budget for food?')\n7. Show recent expenses (e.g., 'Show my last 5 expenses')",
                "error": None
            }
            
        except Exception as e:
            LOGGER.error(f"Error processing message: {e}")
            return {
                "response": "Sorry, I encountered an error processing your message. Please try again.",
                "error": str(e)
            }
    