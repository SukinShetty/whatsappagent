import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

def setup_database():
    """Set up the SQLite database with necessary tables."""
    logger.info("Setting up the database...")
    
    # Ensure the data directory exists
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(data_dir, exist_ok=True)
    
    db_path = os.path.join(data_dir, "links.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create table for links
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        link TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create table for reminders
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        task TEXT NOT NULL,
        reminder_time DATETIME NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        completed BOOLEAN DEFAULT 0
    )
    ''')
    
    # Create table for shown links (to handle "yes" responses)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS shown_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        link TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    conn.close()
    logger.info(f"Database setup complete. Database created at {db_path}")
    return db_path

def reset_shown_links():
    """Clear out the shown_links table to start fresh."""
    logger.info("Resetting shown_links table...")
    
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    db_path = os.path.join(data_dir, "links.db")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Delete all records from shown_links
        cursor.execute("DELETE FROM shown_links")
        
        # Commit the changes
        conn.commit()
        logger.info("Successfully reset shown_links table.")
    except Exception as e:
        logger.error(f"Error resetting shown_links table: {e}")
    finally:
        if conn:
            conn.close()

def reset_database():
    """Reset the database completely for a fresh start"""
    logger.info("Resetting database completely...")
    
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    db_path = os.path.join(data_dir, "links.db")
    
    # If file exists, delete it first
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
            logger.info(f"Deleted existing database at {db_path}")
        except Exception as e:
            logger.error(f"Error deleting database: {e}")
    
    # Then recreate from scratch
    return setup_database()

# Call this at the bottom of the file to reset the database on server start
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    db_path = reset_database()
    print(f"Database reset and recreated at {db_path}") 