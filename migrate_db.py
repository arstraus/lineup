import database
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.sql import text

def add_user_id_column():
    """Add user_id column to teams table if it doesn't exist"""
    # Get engine and connection
    engine = database.engine
    
    # Check if the users table exists
    with engine.connect() as conn:
        # First create users table if it doesn't exist
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR NOT NULL UNIQUE,
            password_hash VARCHAR NOT NULL,
            salt VARCHAR NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """))
        
        # Check if user_id column exists in teams table
        result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'teams' AND column_name = 'user_id'
        """))
        
        # If user_id column doesn't exist, add it
        if result.rowcount == 0:
            conn.execute(text("""
            ALTER TABLE teams 
            ADD COLUMN user_id INTEGER,
            ADD CONSTRAINT fk_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            """))
            print("Added user_id column to teams table")
        else:
            print("user_id column already exists in teams table")
        
        conn.commit()

if __name__ == "__main__":
    add_user_id_column()
    print("Database migration completed successfully")