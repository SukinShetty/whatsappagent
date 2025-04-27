import os
import sys
import sqlite3
from datetime import datetime, timedelta
import re

# Add the project root to the Python path
sys.path.append(os.path.abspath("."))

# Setup the database
def setup_database():
    data_dir = os.path.join("src", "langgraph_whatsapp", "data")
    os.makedirs(data_dir, exist_ok=True)
    
    db_path = os.path.join(data_dir, "links.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create links table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        link TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create reminders table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        task TEXT NOT NULL,
        reminder_time DATETIME NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        triggered BOOLEAN DEFAULT 0
    )
    ''')
    
    conn.commit()
    conn.close()
    return db_path

# Simple save_link function
def save_link(user_id, link):
    if not user_id or not link:
        return "Error: Both user_id and link are required."
    
    # Simple URL validation
    if not (link.startswith('http://') or link.startswith('https://')):
        return f"Error: '{link}' doesn't appear to be a valid URL. It should start with http:// or https://"
    
    try:
        # Setup the database first
        setup_database()
        
        # Open connection and save the link
        data_dir = os.path.join("src", "langgraph_whatsapp", "data")
        db_path = os.path.join(data_dir, "links.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO links (user_id, link) VALUES (?, ?)", (user_id, link))
        conn.commit()
        conn.close()
        return f"Link '{link}' saved successfully."
    except Exception as e:
        return f"An error occurred: {e}"

# Simple retrieve_links function
def retrieve_links(user_id):
    if not user_id:
        return "Error: user_id is required."
    
    try:
        # Setup the database first
        setup_database()
        
        # Open connection and retrieve links
        data_dir = os.path.join("src", "langgraph_whatsapp", "data")
        db_path = os.path.join(data_dir, "links.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT link FROM links WHERE user_id = ? ORDER BY timestamp DESC", (user_id,))
        links = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        if not links:
            return "You don't have any saved links yet."
        
        result = "Your saved links:\n\n"
        for i, link in enumerate(links, 1):
            result += f"{i}. {link}\n"
        return result
    except Exception as e:
        return f"An error occurred: {e}"

# Simple extract_links function
def extract_links(text):
    if not text:
        return []
    
    # Simple regex for URLs
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
    return re.findall(url_pattern, text)

# Test user ID
user_id = "whatsapp:+1234567890"

# Run the tests
if __name__ == "__main__":
    # Test save_link
    print("Testing save_link...")
    link = "https://example.com"
    result = save_link(user_id, link)
    print(f"Save link result: {result}")
    
    # Test retrieve_links
    print("\nTesting retrieve_links...")
    result = retrieve_links(user_id)
    print(f"Retrieve links result: {result}")
    
    # Test extract_links
    print("\nTesting extract_links...")
    message = "Check out this article: https://example.com and also this one: https://github.com"
    links = extract_links(message)
    print(f"Extracted links: {links}") 