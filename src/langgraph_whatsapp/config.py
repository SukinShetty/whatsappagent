from dotenv import load_dotenv, find_dotenv
import os
import logging

LOGGER = logging.getLogger("config")

# Load environment variables from .env file if present
load_dotenv(find_dotenv())

LANGGRAPH_URL = os.getenv("LANGGRAPH_URL", "http://localhost:8081")
ASSISTANT_ID = os.getenv("ASSISTANT_ID", "whatsapp_agent")
CONFIG = os.getenv("CONFIG") or "{}"

# Twilio configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE_NUMBER:
    LOGGER.warning("Twilio credentials not found in environment variables.")
    LOGGER.warning("Using hard-coded values for testing - NEVER DO THIS IN PRODUCTION!")
    # Fallback testing values - NEVER USE THESE IN PRODUCTION
    TWILIO_ACCOUNT_SID = "AC590ae2b260a5a1ee9819fc0b89a9e3c7"  # From your logs
    TWILIO_AUTH_TOKEN = "your_auth_token_here"  # You need to set this
    TWILIO_PHONE_NUMBER = "whatsapp:+14155238886"  # From your logs