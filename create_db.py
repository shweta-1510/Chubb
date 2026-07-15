"""
Create database if it doesn't exist.
"""
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys
import os
from dotenv import load_dotenv

load_dotenv()

# Database connection parameters from environment
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USERNAME", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "health_monitor")

if not DB_PASSWORD:
    print("❌ DB_PASSWORD is not set in .env file")
    sys.exit(1)

def create_database():
    """Create the health_monitor database if it doesn't exist."""
    try:
        # Connect to PostgreSQL server (to the default 'postgres' database)
        print(f"Connecting to PostgreSQL at {DB_HOST}:{DB_PORT}...")
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute(
            "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
            (DB_NAME,)
        )
        exists = cursor.fetchone()
        
        if exists:
            print(f"✅ Database '{DB_NAME}' already exists")
        else:
            # Create database
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(
                sql.Identifier(DB_NAME)
            ))
            print(f"✅ Database '{DB_NAME}' created successfully!")
        
        cursor.close()
        conn.close()
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Error creating database: {e}")
        print(f"\nPlease verify:")
        print(f"  1. PostgreSQL is running")
        print(f"  2. Username and password are correct in .env file")
        print(f"  3. PostgreSQL is listening on port {DB_PORT}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    if create_database():
        sys.exit(0)
    else:
        sys.exit(1)
