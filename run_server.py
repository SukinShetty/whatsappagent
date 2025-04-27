import uvicorn
from fastapi import FastAPI, Request, Form, Response
from src.langgraph_whatsapp.server import APP, WSP_AGENT
import logging
from src.langgraph_whatsapp.database_setup import reset_database

# Reset database on startup
logger = logging.getLogger(__name__)
logger.info("Resetting database for fresh start")
reset_database()

# Configure logging
logging.basicConfig(level=logging.DEBUG)

@APP.get("/")
async def root():
    logger.debug("Root endpoint called")
    return {"message": "WhatsApp Agent Server is running!"}

@APP.post("/")
async def root_post(request: Request):
    try:
        # Try to parse form data first (which is what Twilio sends)
        form_data = await request.form()
        if "From" in form_data and "Body" in form_data:
            logger.info(f"Received WhatsApp message from {form_data['From']}: {form_data['Body']}")
            # Forward to WhatsApp handler
            xml = await WSP_AGENT.handle_message(request)
            logger.debug(f"Sending response: {xml}")
            return Response(
                content=xml,
                media_type="text/xml",
                headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "Cache-Control": "no-cache",
                    "X-Powered-By": "FastAPI"
                }
            )
        
        # If not form data, try JSON
        body = await request.json()
        logger.debug(f"POST request received with body: {body}")
        return {"message": "POST request received", "data": body}
    except Exception as e:
        logger.error(f"Error in root_post: {str(e)}")
        try:
            # Last attempt - check if it's a WhatsApp request without properly parsing
            # Get the raw body and check for WhatsApp-related fields
            raw_body = await request.body()
            body_str = raw_body.decode()
            
            if "From=" in body_str and "Body=" in body_str:
                logger.info("Detected WhatsApp message in raw body, forwarding to handler")
                # Rewind the request body for the handler
                async def _replay():
                    return {"type": "http.request", "body": raw_body, "more_body": False}
                request._body = raw_body
                request._receive = _replay
                
                # Forward to WhatsApp handler
                xml = await WSP_AGENT.handle_message(request)
                logger.debug(f"Sending response: {xml}")
                return Response(
                    content=xml,
                    media_type="text/xml",
                    headers={
                        "Content-Type": "text/xml; charset=utf-8",
                        "Cache-Control": "no-cache",
                        "X-Powered-By": "FastAPI"
                    }
                )
        except Exception as inner_e:
            logger.error(f"Error processing potential WhatsApp message: {inner_e}")
            # Return a proper TwiML error response
            from twilio.twiml.messaging_response import MessagingResponse
            twiml = MessagingResponse()
            msg = twiml.message()
            msg.body("I'm sorry, I encountered a technical issue. Please try again later.")
            error_response = f'<?xml version="1.0" encoding="UTF-8"?>{str(twiml)}'
            return Response(
                content=error_response,
                media_type="text/xml",
                headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "Cache-Control": "no-cache",
                    "X-Powered-By": "FastAPI"
                }
            )
            
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response><Message>Error processing request</Message></Response>',
            media_type="text/xml",
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "Cache-Control": "no-cache",
                "X-Powered-By": "FastAPI"
            }
        )

@APP.post("/test-whatsapp")
async def test_whatsapp(From: str = Form(...), Body: str = Form(...)):
    return {
        "message": "WhatsApp message received successfully", 
        "from": From, 
        "body": Body
    }

@APP.get("/test")
async def test():
    logger.debug("Test endpoint called")
    return {"status": "ok", "message": "Test endpoint working"}

if __name__ == "__main__":
    logger.info("Starting server on http://127.0.0.1:8081")
    uvicorn.run(APP, host="127.0.0.1", port=8081, log_level="debug") 