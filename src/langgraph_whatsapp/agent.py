import logging
import json
import uuid
from src.langgraph_whatsapp.tools import extract_links, save_link, retrieve_links, set_reminder
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
            
            # FIRST PRIORITY: Check for reminder requests
            if "remind" in msg_lower:
                try:
                    # Extract time and task from message
                    # Common patterns: "remind me to X at Y", "remind me at Y to X"
                    msg_parts = user_message.split(" at ")
                    if len(msg_parts) == 2:
                        task = msg_parts[0].replace("remind me to ", "").replace("remind me ", "").strip()
                        time_str = msg_parts[1].strip()
                        
                        result = set_reminder(id, time_str, task)
                        return {
                            "response": result,
                            "error": None
                        }
                    else:
                        return {
                            "response": "I couldn't understand the reminder format. Please use format like: 'remind me to [task] at [time]'",
                            "error": None
                        }
                except Exception as e:
                    LOGGER.error(f"Error setting reminder: {e}")
                    return {
                        "response": "Sorry, I couldn't set that reminder. Please try again.",
                        "error": str(e)
                    }
            
            # SECOND PRIORITY: Handle saving new links if present in message
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
            
            # THIRD PRIORITY: Check if the message is asking for saved links
            if any(keyword in msg_lower for keyword in ["show", "get", "my", "share", "find"]) and any(keyword in msg_lower for keyword in ["link", "links", "repo", "repository"]):
                try:
                    # Get all links first
                    all_links = retrieve_links(id)
                    
                    # Filter links based on keywords in the user's message
                    filtered_links = all_links
                    
                    # Filter for specific types of links
                    if "x.com" in msg_lower or "twitter" in msg_lower:
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
                            "response": "I couldn't find any matching links for your request.",
                            "error": None
                        }
                except Exception as e:
                    LOGGER.error(f"Error retrieving links: {e}")
                    return {
                        "response": "Sorry, I couldn't retrieve your links. Please try again.",
                        "error": str(e)
                    }
            
            # Default response for other messages
            return {
                "response": "I can help you save and retrieve links, and set reminders! Just:\n- Send me a link to save it\n- Ask me to show your links\n- Say 'remind me to [task] at [time]'",
                "error": None
            }
            
        except Exception as e:
            LOGGER.error(f"Error processing message: {e}")
            return {
                "response": "I encountered an error. Please try again.",
                "error": str(e)
            }
    