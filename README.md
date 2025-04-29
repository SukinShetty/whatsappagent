# WhatsApp Finance Assistant

A WhatsApp bot that helps you manage your personal finances, schedule meetings, set reminders, and save links.

## Features

### Financial Management
- Track expenses with natural language
  - "I spent 500 on groceries"
  - "I have spent 300 on transportation"
  - "I paid 1000 for rent"
  - "I bought food for 200"
  - "I used 300 on transportation"

- Check budget status
  - "What's my budget for groceries?"
  - "How much can I spend on food?"
  - "Check budget for entertainment"

- View recent expenses
  - "Show my last 5 expenses"
  - "List recent expenses"
  - "Show spending history"

### Calendar Management
- Book meetings and events
  - "Book a meeting with John at 3 PM"
  - "Schedule a call tomorrow at 9 AM"
  - "Create appointment with dentist on Friday"

### Reminders
- Set reminders with natural language
  - "Remind me to call John at 3pm"
  - "Remind me tomorrow to check email"
  - "Remind me in 2 hours to take a break"

### Link Management
- Save and retrieve links
  - Automatically saves shared links
  - "Show my saved links"
  - "Find my GitHub links"
  - "Get my Twitter links"

## Setup

1. Create a Google Cloud project and enable Google Sheets API
2. Set up OAuth 2.0 credentials and save as `sheets_credentials.json`
3. Create a Google Spreadsheet with "Expenses" and "Budgets" tabs
4. Update the spreadsheet ID in your configuration

## Usage

1. Start the server: `python run_server.py`
2. Connect your WhatsApp account
3. Start chatting with the bot using natural language commands

## Dependencies

- Google Sheets API
- SQLite for local storage
- Python WhatsApp Web API