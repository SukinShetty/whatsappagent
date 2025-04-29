import os
import logging
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle
from datetime import datetime

logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file sheets_token.pickle.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Create your own spreadsheet instead of using a placeholder
# The ID is automatically set after creating a new spreadsheet
SPREADSHEET_ID = None

# Define the sheets and ranges
EXPENSES_SHEET = 'Expenses'
BUDGETS_SHEET = 'Budgets'
EXPENSES_RANGE = 'A:C'  # Date, Amount, Category
BUDGETS_RANGE = 'A:B'   # Category, Budget Amount

def get_sheets_service():
    """Get a Google Sheets service object for making API calls."""
    creds = None
    # The file token.pickle stores the user's access and refresh tokens
    token_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'sheets_token.pickle')
    credentials_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'sheets_credentials.json')
    
    # Ensure the data directory exists
    os.makedirs(os.path.dirname(token_file), exist_ok=True)
    
    # Check if token.pickle exists with saved credentials
    if os.path.exists(token_file):
        logger.info(f"Loading sheets credentials from {token_file}")
        try:
            with open(token_file, 'rb') as token:
                creds = pickle.load(token)
        except Exception as e:
            logger.error(f"Error loading sheets token file: {e}")
    
    # If no valid credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired sheets credentials")
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.error(f"Error refreshing sheets credentials: {e}")
                creds = None
        
        if not creds:
            if not os.path.exists(credentials_file):
                logger.error(f"Sheets credentials file not found at {credentials_file}")
                logger.error("Please download sheets_credentials.json from Google Cloud Console")
                logger.error("1. Go to https://console.cloud.google.com/")
                logger.error("2. Create a project and enable Google Sheets API")
                logger.error("3. Create OAuth credentials and download as sheets_credentials.json")
                logger.error("4. Place the file in the data directory")
                return None
                
            logger.info(f"Getting fresh sheets credentials using {credentials_file}")
            try:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e:
                logger.error(f"Error during sheets authentication flow: {e}")
                return None
                
            # Save the credentials for the next run
            with open(token_file, 'wb') as token:
                pickle.dump(creds, token)
                logger.info(f"Saved sheets credentials to {token_file}")
    
    try:
        service = build('sheets', 'v4', credentials=creds)
        logger.info("Google Sheets service created successfully")
        return service
    except Exception as e:
        logger.error(f"Error building sheets service: {e}")
        return None

def setup_spreadsheet():
    """Create a new spreadsheet with the required sheets and columns if it doesn't exist."""
    global SPREADSHEET_ID
    
    # Check if we already have a spreadsheet ID stored
    spreadsheet_id_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'spreadsheet_id.txt')
    
    if os.path.exists(spreadsheet_id_file):
        with open(spreadsheet_id_file, 'r') as f:
            SPREADSHEET_ID = f.read().strip()
            logger.info(f"Using existing spreadsheet ID: {SPREADSHEET_ID}")
            return SPREADSHEET_ID
    
    # No spreadsheet ID found, create a new one
    service = get_sheets_service()
    if not service:
        logger.error("Could not get sheets service to create spreadsheet")
        return None
    
    try:
        # Create a new spreadsheet
        spreadsheet = {
            'properties': {
                'title': 'WhatsApp Finance Tracker'
            },
            'sheets': [
                {
                    'properties': {
                        'title': EXPENSES_SHEET
                    }
                },
                {
                    'properties': {
                        'title': BUDGETS_SHEET
                    }
                }
            ]
        }
        
        spreadsheet = service.spreadsheets().create(body=spreadsheet).execute()
        SPREADSHEET_ID = spreadsheet['spreadsheetId']
        logger.info(f"Created new spreadsheet with ID: {SPREADSHEET_ID}")
        
        # Save the spreadsheet ID for future use
        with open(spreadsheet_id_file, 'w') as f:
            f.write(SPREADSHEET_ID)
        
        # Add headers to Expenses sheet
        values = [['Date', 'Amount', 'Category']]
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f'{EXPENSES_SHEET}!A1:C1',
            valueInputOption='RAW',
            body={'values': values}
        ).execute()
        
        # Add headers and comprehensive categories to Budgets sheet
        values = [
            ['Category', 'Budget Amount'],
            ['Groceries', 3000],
            ['Food', 5000],
            ['Dining', 2000],
            ['Restaurant', 2000],
            ['Entertainment', 1500],
            ['Movies', 1000],
            ['Shopping', 3000],
            ['Clothing', 2000],
            ['Transportation', 1000],
            ['Travel', 5000],
            ['Fuel', 2000],
            ['Gas', 2000],
            ['Petrol', 2000],
            ['Rent', 10000],
            ['Housing', 10000],
            ['Utilities', 2000],
            ['Electricity', 1000],
            ['Water', 500],
            ['Internet', 1000],
            ['Phone', 1000],
            ['Mobile', 1000],
            ['Education', 3000],
            ['Books', 1000],
            ['Courses', 2000],
            ['Healthcare', 5000],
            ['Medical', 5000],
            ['Medicine', 1000],
            ['Insurance', 3000],
            ['Gifts', 1000],
            ['Donations', 1000],
            ['Subscriptions', 1000],
            ['Streaming', 500],
            ['Miscellaneous', 2000],
            ['Other', 1000]
        ]
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f'{BUDGETS_SHEET}!A1:B{len(values)}',
            valueInputOption='RAW',
            body={'values': values}
        ).execute()
        
        logger.info(f"Spreadsheet setup complete. URL: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")
        return SPREADSHEET_ID
        
    except Exception as e:
        logger.error(f"Error creating spreadsheet: {e}")
        return None

# Make sure we have a valid spreadsheet ID
if not SPREADSHEET_ID:
    SPREADSHEET_ID = setup_spreadsheet()

def add_expense(amount, category):
    """Add an expense to the Google Sheet."""
    global SPREADSHEET_ID
    
    # Ensure we have a valid spreadsheet
    if not SPREADSHEET_ID:
        SPREADSHEET_ID = setup_spreadsheet()
        if not SPREADSHEET_ID:
            return "Could not create or access Google Sheet. Please try again later."
    
    service = get_sheets_service()
    if not service:
        return "Could not connect to Google Sheets. Please check your credentials."
    
    try:
        # Format today's date
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Clean up and standardize the category
        category = category.lower().strip()
        # Remove common words that might be appended
        category = category.split(' is')[0].strip()
        category = category.split(' for')[0].strip()
        category = category.split(' on')[0].strip()
        category = category.split(' in')[0].strip()
        
        # Try to match with an existing category
        budget_result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f'{BUDGETS_SHEET}!A1:B100'
        ).execute()
        
        budget_rows = budget_result.get('values', [])
        matched_category = None
        
        # First try exact match
        for row in budget_rows[1:]:  # Skip header row
            if len(row) >= 1 and row[0].lower() == category:
                matched_category = row[0]
                break
        
        # If no exact match, try to find a category that contains the search term
        if not matched_category:
            for row in budget_rows[1:]:
                if len(row) >= 1 and (
                    category in row[0].lower() or
                    row[0].lower() in category
                ):
                    matched_category = row[0]
                    break
        
        # Use the matched category if found, otherwise use original with first letter capitalized
        if matched_category:
            category = matched_category
        else:
            # Capitalize first letter of each word for better formatting
            category = ' '.join(word.capitalize() for word in category.split())
        
        # Prepare the data to append
        values = [[today, amount, category]]
        
        # Append to the expenses sheet
        body = {'values': values}
        result = service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f'{EXPENSES_SHEET}!A2',
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        
        return f"Added expense: {amount} for {category}"
    
    except Exception as e:
        logger.error(f"Error adding expense: {e}")
        return f"Error adding expense: {e}"

def check_budget(category):
    """Check budget for a specific category."""
    global SPREADSHEET_ID
    
    # Ensure we have a valid spreadsheet
    if not SPREADSHEET_ID:
        SPREADSHEET_ID = setup_spreadsheet()
        if not SPREADSHEET_ID:
            return "Could not create or access Google Sheet. Please try again later."
    
    service = get_sheets_service()
    if not service:
        return "Could not connect to Google Sheets. Please check your credentials."
    
    try:
        # Check if requesting all budgets
        if category.lower() == "all":
            # Get all budget categories and amounts
            budget_result = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=f'{BUDGETS_SHEET}!A1:B100'
            ).execute()
            
            budget_rows = budget_result.get('values', [])
            if not budget_rows or len(budget_rows) <= 1:
                return "No budget data found."
            
            # Create a formatted response with all budget categories
            response = "this is the budget\n"
            
            # Get top categories with higher budgets (up to 8)
            top_categories = []
            for row in budget_rows[1:]:  # Skip header
                if len(row) >= 2:
                    category_name = row[0]
                    try:
                        budget_amount = float(row[1])
                        # Add only main categories, avoiding duplicates like Food/Dining
                        # and categories with higher budgets
                        if len(top_categories) < 8 and not any(cat.startswith(category_name.split()[0]) for cat, _ in top_categories):
                            top_categories.append((category_name, budget_amount))
                    except ValueError:
                        continue
            
            # Sort by budget amount (highest first)
            top_categories.sort(key=lambda x: x[1], reverse=True)
            
            # Format the response
            for category_name, budget_amount in top_categories[:5]:  # Display top 5
                response += f"{category_name} - {int(budget_amount)}\n"
                
            return response.strip()
            
        # Clean up the category input - remove common words and trailing words like "is", "for", etc.
        category = category.lower().strip()
        # Remove common words that might be appended
        category = category.split(' is')[0].strip()
        category = category.split(' for')[0].strip()
        category = category.split(' on')[0].strip()
        category = category.split(' in')[0].strip()
        
        logger.info(f"Cleaned category for budget check: '{category}'")
        
        # Get budgets
        budget_result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f'{BUDGETS_SHEET}!A1:B100'
        ).execute()
        
        budget_rows = budget_result.get('values', [])
        if not budget_rows:
            return "No budget data found."
        
        # Find budget for the specified category
        budget_amount = 0
        matched_category = None
        
        # First try exact match
        for row in budget_rows[1:]:  # Skip header row
            if len(row) >= 2 and row[0].lower() == category:
                budget_amount = float(row[1])
                matched_category = row[0]
                break
        
        # If no exact match, try to find a category that contains the search term
        if budget_amount == 0:
            for row in budget_rows[1:]:
                if len(row) >= 2 and (
                    category in row[0].lower() or
                    row[0].lower() in category
                ):
                    budget_amount = float(row[1])
                    matched_category = row[0]
                    break
        
        if budget_amount == 0:
            # Get all available categories for the error message
            categories = [row[0] for row in budget_rows[1:] if len(row) >= 1]
            categories_str = ", ".join(categories[:10])  # Show first 10 categories
            if len(categories) > 10:
                categories_str += "..."
                
            return f"No budget found for category: {category}. Available categories: {categories_str}"
        
        # Get expenses for the current month
        current_month = datetime.now().strftime('%Y-%m')
        
        expense_result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f'{EXPENSES_SHEET}!A1:C100'
        ).execute()
        
        expense_rows = expense_result.get('values', [])
        if not expense_rows or len(expense_rows) <= 1:
            return f"Budget for {matched_category}: {budget_amount}. No expenses recorded yet."
        
        # Calculate total expenses for the category this month
        total_spent = 0
        for row in expense_rows[1:]:  # Skip header row
            if len(row) >= 3:
                expense_date = row[0]
                expense_amount = float(row[1])
                expense_category = row[2].lower()
                
                # Check if expense is from current month and for the specified category
                # Use flexible matching for categories
                if expense_date.startswith(current_month) and (
                    expense_category == category.lower() or
                    category.lower() in expense_category or
                    expense_category in category.lower() or
                    expense_category == matched_category.lower()
                ):
                    total_spent += expense_amount
        
        # Calculate remaining budget
        remaining = budget_amount - total_spent
        
        return f"Budget for {matched_category}: {budget_amount}\nSpent this month: {total_spent}\nRemaining: {remaining}"
    
    except Exception as e:
        logger.error(f"Error checking budget: {e}")
        return f"Error checking budget: {e}"

def list_recent_expenses(limit=5):
    """List the most recent expenses."""
    global SPREADSHEET_ID
    
    # Ensure we have a valid spreadsheet
    if not SPREADSHEET_ID:
        SPREADSHEET_ID = setup_spreadsheet()
        if not SPREADSHEET_ID:
            return "Could not create or access Google Sheet. Please try again later."
    
    service = get_sheets_service()
    if not service:
        return "Could not connect to Google Sheets. Please check your credentials."
    
    try:
        # Get expenses
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f'{EXPENSES_SHEET}!A1:C100'
        ).execute()
        
        rows = result.get('values', [])
        if not rows or len(rows) <= 1:
            return "No expenses found."
        
        # Skip header and get the last 'limit' rows
        recent_expenses = rows[1:] if len(rows) > 1 else []
        recent_expenses = recent_expenses[-limit:]
        
        if not recent_expenses:
            return "No recent expenses found."
        
        # Format the response
        response = "Recent expenses:\n"
        for expense in recent_expenses:
            if len(expense) >= 3:
                date = expense[0]
                amount = expense[1]
                category = expense[2]
                response += f"- {date}: {amount} on {category}\n"
        
        return response
    
    except Exception as e:
        logger.error(f"Error listing expenses: {e}")
        return f"Error listing expenses: {e}"

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Force create a new spreadsheet
    force_new = True
    if force_new:
        spreadsheet_id_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'spreadsheet_id.txt')
        if os.path.exists(spreadsheet_id_file):
            os.remove(spreadsheet_id_file)
            print("Deleted old spreadsheet ID file to create a new one")
    
    # Test the setup
    spreadsheet_id = setup_spreadsheet()
    if spreadsheet_id:
        print(f"Google Sheets API connection successful!")
        print(f"Spreadsheet URL: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
    else:
        print("Failed to set up Google Sheets API connection") 