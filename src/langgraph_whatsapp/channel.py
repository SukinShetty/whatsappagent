# channel.py
import base64, logging, requests
from abc import ABC, abstractmethod

from fastapi import Request, HTTPException
from twilio.twiml.messaging_response import MessagingResponse

from src.langgraph_whatsapp.agent import Agent
from src.langgraph_whatsapp.config import TWILIO_AUTH_TOKEN, TWILIO_ACCOUNT_SID

LOGGER = logging.getLogger("whatsapp")


def twilio_url_to_data_uri(url: str, content_type: str = None) -> str:
    """Download the Twilio media URL and convert to data‑URI (base64)."""
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN):
        raise RuntimeError("Twilio credentials are missing")

    LOGGER.info(f"Downloading image from Twilio URL: {url}")
    resp = requests.get(url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), timeout=20)
    resp.raise_for_status()

    # Use provided content_type or get from headers
    mime = content_type or resp.headers.get('Content-Type')

    # Ensure we have a proper image mime type
    if not mime or not mime.startswith('image/'):
        LOGGER.warning(f"Converting non-image MIME type '{mime}' to 'image/jpeg'")
        mime = "image/jpeg"  # Default to jpeg if not an image type

    b64 = base64.b64encode(resp.content).decode()
    data_uri = f"data:{mime};base64,{b64}"

    return data_uri

class WhatsAppAgent(ABC):
    @abstractmethod
    async def handle_message(self, request: Request) -> str: ...

class WhatsAppAgentTwilio(WhatsAppAgent):
    def __init__(self) -> None:
        if not (TWILIO_AUTH_TOKEN and TWILIO_ACCOUNT_SID):
            raise ValueError("Twilio credentials are not configured")
        self.agent = Agent()

    async def handle_message(self, request: Request) -> str:
        try:
            LOGGER.info("Receiving WhatsApp message request")
            form = await request.form()
            
            # Log all form data for debugging
            LOGGER.debug(f"Received WhatsApp form data: {dict(form)}")

            sender = form.get("From", "").strip()
            content = form.get("Body", "").strip()
            
            if not sender:
                LOGGER.error("Missing 'From' field in request form")
                raise HTTPException(400, detail="Missing 'From' in request form")
                
            LOGGER.info(f"Processing message from {sender}: {content[:50]}{'...' if len(content) > 50 else ''}")

            # Collect ALL images
            images = []
            num_media = int(form.get("NumMedia", "0"))
            LOGGER.info(f"Message contains {num_media} media attachments")
            
            for i in range(num_media):
                url = form.get(f"MediaUrl{i}", "")
                ctype = form.get(f"MediaContentType{i}", "")
                if url and ctype.startswith("image/"):
                    try:
                        LOGGER.info(f"Processing image {i+1}/{num_media} of type {ctype}")
                        images.append({
                            "url": url,
                            "data_uri": twilio_url_to_data_uri(url, ctype),
                        })
                    except Exception as err:
                        LOGGER.error(f"Failed to download image from {url}: {err}")

            LOGGER.info(f"Invoking agent with sender ID: {sender}")
            response = await self.agent.invoke(sender, content, images if images else None)
            
            # Extract response text from the new format
            reply = response.get('response', "I'm sorry, I encountered a technical issue.")
            LOGGER.info(f"Agent response: {reply[:50]}{'...' if len(reply) > 50 else ''}")

            # Create TwiML response
            twiml = MessagingResponse()
            msg = twiml.message()
            msg.body(reply)  # Use body() method to set message content
            response_xml = str(twiml)  # TwiML already includes XML declaration
            LOGGER.debug(f"Generated TwiML response: {response_xml}")
            return response_xml
            
        except Exception as e:
            LOGGER.exception(f"Error handling WhatsApp message: {str(e)}")
            # Return a fallback response instead of crashing
            twiml = MessagingResponse()
            msg = twiml.message()
            msg.body("I'm sorry, I encountered a technical issue. Please try again later.")
            return str(twiml)
