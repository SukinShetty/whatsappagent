# LangGraph WhatsApp Agent

This WhatsApp agent is built using the LangGraph framework. It allows you to interact with an AI assistant through WhatsApp, with capabilities to save links and set reminders.

## Features

- Link Management: Store and retrieve links shared during conversations
- Reminders: Set reminders for tasks at specific times
- Image Processing: The agent can process images shared in WhatsApp

## Setup Instructions

### 1. Prerequisites

- Python 3.11 or higher
- A Twilio account with WhatsApp sandbox configured
- LangGraph server (local or remote)

### 2. Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/langgraph-whatsapp-agent.git
   cd langgraph-whatsapp-agent
   ```

2. Install the dependencies:
   ```
   pip install -e .
   ```

3. Copy `.env.example` to `.env` and add your credentials:
   ```
   cp .env.example .env
   ```

4. Edit the `.env` file with your Twilio credentials and other settings.

### 3. Running the Agent

1. Start the LangGraph server if you're running it locally:
   ```
   langraph server start
   ```

2. Run the WhatsApp server:
   ```
   python -m src.langgraph_whatsapp.server
   ```

3. Configure your Twilio WhatsApp Sandbox to point to your webhook:
   - If running locally, you'll need to expose your server (e.g., using ngrok)
   - Set the webhook URL in Twilio to `https://your-domain.com/whatsapp`

## Usage

Once set up, you can interact with the agent through WhatsApp:

1. **Save links**: Share a link or URL in a message, and the agent will offer to save it for you.

2. **Retrieve links**: Ask "Show me my saved links" or "What links do I have?"

3. **Set reminders**: Send a message like "Remind me to call John at 3 PM tomorrow" and the agent will set a reminder.

## Development

### Database

The agent uses SQLite to store:
- Links shared by users
- Reminders created by users

The database is automatically created at `src/langgraph_whatsapp/data/links.db`.

### Adding New Tools

To add new capabilities to the agent:
1. Add new functions in `src/langgraph_whatsapp/tools.py`
2. Decorate them with `@tool`
3. Add them to the `all_tools` list
4. Update the system prompt in `enhance_system_prompt` method in `agent.py`

## License

This project is licensed under the terms included in the LICENSE file.