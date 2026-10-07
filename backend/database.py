import os
import sqlite3

# Define default database path inside the database/ directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "..", "database", "app.db")

def get_db_connection(db_path=None):
    """
    Creates and returns a connection to the SQLite database.
    - Enables foreign key support.
    - Sets row_factory to sqlite3.Row for dictionary-like column access.
    """
    if db_path is None:
        db_path = os.environ.get("DATABASE_PATH", DEFAULT_DB_PATH)
    
    # Ensure parent directory exists
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    
    # Timeout 10s helps prevent SQLite busy errors during concurrency
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(db_path=None):
    """
    Initializes database tables:
    1. users: Stores user login credentials and roles ('admin' or 'member').
    2. events: Stores event details, capacity, and current registered count.
    3. registrations: Tracks user-to-event registrations with unique constraint.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # 1. Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin', 'member')) DEFAULT 'member',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 2. Events table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            date TEXT NOT NULL,
            location TEXT NOT NULL,
            capacity INTEGER NOT NULL CHECK (capacity > 0),
            registered_count INTEGER NOT NULL DEFAULT 0 CHECK (registered_count >= 0),
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE CASCADE
        );
    """)

    # 3. Registrations table (Many-to-Many junction table)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_id INTEGER NOT NULL,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE,
            UNIQUE (user_id, event_id)
        );
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DEFAULT_DB_PATH)
