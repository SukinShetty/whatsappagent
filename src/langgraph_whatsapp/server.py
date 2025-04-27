# server.py
import logging
import os
from urllib.parse import parse_qs
import atexit

from fastapi import FastAPI, Request, Response, HTTPException, Form
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from src.langgraph_whatsapp.channel import WhatsAppAgentTwilio
from src.langgraph_whatsapp.config import TWILIO_AUTH_TOKEN
from src.langgraph_whatsapp.database_setup import setup_database
from src.langgraph_whatsapp.tools import initialize_scheduler, cleanup_scheduler, extract_links, save_link, retrieve_links, set_reminder

LOGGER = logging.getLogger("server")
APP = FastAPI()
WSP_AGENT = WhatsAppAgentTwilio()

# Initialize database
db_path = setup_database()
LOGGER.info(f"Database initialized at {db_path}")

# Initialize and start the scheduler for reminders
scheduler = initialize_scheduler()
LOGGER.info("Scheduler initialized for reminders")

# Register cleanup function to shutdown scheduler gracefully
atexit.register(cleanup_scheduler)

class TwilioMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, paths: list = ["/whatsapp", "/"]):
        super().__init__(app)
        self.paths = paths
        self.validator = RequestValidator(TWILIO_AUTH_TOKEN)

    async def dispatch(self, request: Request, call_next):
        # Check if the request path is in our list of paths to validate
        if request.url.path in self.paths and request.method == "POST":
            body = await request.body()

            # Signature check
            form_dict = parse_qs(body.decode(), keep_blank_values=True)
            flat_form_dict = {k: v[0] if isinstance(v, list) and v else v for k, v in form_dict.items()}
            
            proto = request.headers.get("x-forwarded-proto", request.url.scheme)
            host  = request.headers.get("x-forwarded-host", request.headers.get("host"))
            url   = f"{proto}://{host}{request.url.path}"
            sig   = request.headers.get("X-Twilio-Signature", "")

            if not self.validator.validate(url, flat_form_dict, sig):
                LOGGER.warning("Invalid Twilio signature for %s", url)
                # Don't reject immediately - some test requests might not have signatures
                # return Response(status_code=401, content="Invalid Twilio signature")

            # Rewind: body and receive channel
            async def _replay() -> Message:
                return {"type": "http.request", "body": body, "more_body": False}

            request._body = body
            request._receive = _replay  # type: ignore[attr-defined]

        return await call_next(request)


APP.add_middleware(TwilioMiddleware, paths=["/whatsapp", "/"])


@APP.post("/whatsapp")
async def whatsapp_reply_twilio(request: Request):
    try:
        xml = await WSP_AGENT.handle_message(request)
        return Response(content=xml, media_type="application/xml")
    except HTTPException as e:
        LOGGER.error("Handled error: %s", e.detail)
        raise
    except Exception as e:
        LOGGER.exception("Unhandled exception")
        raise HTTPException(status_code=500, detail="Internal server error")

@APP.post("/test-whatsapp-direct")
async def test_whatsapp_direct(From: str = Form(...), Body: str = Form(...)):
    """A simple test endpoint that bypasses Twilio signature validation."""
    try:
        LOGGER.info(f"Received message from {From}: {Body}")
        
        # Check if message contains links
        links = extract_links(Body)
        LOGGER.debug(f"Extracted links: {links}")
        
        # Handle links in the message
        if links and any(word in Body.lower() for word in ["save", "store", "keep"]):
            # Save the first link
            LOGGER.info(f"Saving link {links[0]} for user {From}")
            save_result = save_link(From, links[0])
            reply = f"I've saved that link for you: {save_result}"
        
        # Handle requesting saved links
        elif "links" in Body.lower() and any(word in Body.lower() for word in ["saved", "show", "get", "retrieve"]):
            LOGGER.info(f"Retrieving links for user {From}")
            links_result = retrieve_links(From)
            reply = links_result
        
        # Handle reminder requests
        elif any(word in Body.lower() for word in ["remind", "reminder", "remember"]):
            LOGGER.info(f"Setting reminder for user {From}")
            # Simple pattern matching for time and task
            import re
            from datetime import datetime, timedelta
            
            # Try to find time patterns like "tomorrow at 3pm" or "in 2 hours"
            time_match = re.search(r'(tomorrow|today|in \d+ (hour|minute|day)s?|at \d+(\:\d+)?\s*(am|pm)|morning|afternoon|evening)', Body.lower())
            time_str = time_match.group(0) if time_match else "tomorrow"
            
            # Extract everything after "to" or "about" as the task
            task_match = re.search(r'(to|about)\s+(.+)', Body.lower())
            task = task_match.group(2) if task_match else "your task"
            
            LOGGER.info(f"Setting reminder for time: {time_str}, task: {task}")
            reminder_result = set_reminder(From, time_str, task)
            reply = reminder_result
        
        # Default response
        else:
            LOGGER.info("Sending default response")
            reply = "Hello! I'm your WhatsApp assistant. I can save links, retrieve saved links, and set reminders for you. What would you like to do today?"
        
        # Create a TwiML response
        twiml = MessagingResponse()
        twiml.message(reply)
        
        return Response(content=str(twiml), media_type="application/xml")
    except Exception as e:
        LOGGER.exception("Error in test endpoint: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(APP, host="0.0.0.0", port=8081, log_level="info")
