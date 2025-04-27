import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    
    # Create data directory if it doesn't exist
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        
    db_path = os.path.join(data_dir, "links.db")
    
    if not os.path.exists(db_path):
        from src.langgraph_whatsapp.database_setup import setup_database
        setup_database()
        
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn 