from dotenv import load_dotenv
import os
import logging

load_dotenv()  # Loads variables from .env file

LOGGER = logging.getLogger(__name__)

LANGGRAPH_URL = os.getenv("LANGGRAPH_URL", "http://localhost:8081")
ASSISTANT_ID = os.getenv("ASSISTANT_ID", "whatsapp_agent")
CONFIG = os.getenv("CONFIG") or "{}"
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")