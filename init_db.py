"""
Database initialization and migration script.
Run this script to create or update database tables.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database.db import init_db, engine
from app.models.server import ServerModel
from app.models.monitored_service import MonitoredServiceModel
from app.models.health_check_history import HealthCheckHistoryModel
from app.utils.logger import get_logger
from sqlalchemy import inspect

logger = get_logger(__name__)


def check_database_exists() -> bool:
    """Check if database tables exist."""
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        return 'server_management' in tables
    except Exception as e:
        logger.error(f"Error checking database: {e}")
        return False


def main():
    """Main initialization function."""
    print("=" * 60)
    print("Environment Health Check Monitor - Database Setup")
    print("=" * 60)
    print()
    
    # Check if tables already exist
    if check_database_exists():
        print("⚠️  Database tables already exist.")
        response = input("Do you want to recreate them? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Exiting without changes.")
            return
        
        print("⚠️  WARNING: This will delete all existing data!")
        confirm = input("Type 'DELETE' to confirm: ")
        if confirm != 'DELETE':
            print("Operation cancelled.")
            return
        
        # Drop all tables
        print("Dropping existing tables...")
        from app.database.db import Base
        Base.metadata.drop_all(bind=engine)
        print("✅ Tables dropped.")
    
    # Create tables
    print("Creating database tables...")
    try:
        init_db()
        print("✅ Database tables created successfully!")
        print()
        print("Tables created:")
        print("  - server_management")
        print()
        print("You can now start the application with:")
        print("  streamlit run app/main.py")
        print()
        
    except Exception as e:
        print(f"❌ Error creating database tables: {e}")
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
