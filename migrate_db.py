"""
Database migration script to add MonitoredService table.
This script creates the new monitored_services table and migrates existing data.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.db import engine, Base, get_db_context
from app.models.server import ServerModel
from app.models.monitored_service import MonitoredServiceModel
from app.utils.logger import get_logger

logger = get_logger(__name__)


def migrate_database():
    """
    Migrate database schema to support MonitoredService table.
    
    Steps:
    1. Create monitored_services table
    2. Migrate existing services_to_monitor data to new table
    3. Keep services_to_monitor column for backward compatibility (marked as deprecated)
    """
    try:
        logger.info("Starting database migration...")
        
        # Create all tables (including new monitored_services table)
        logger.info("Creating new tables if they don't exist...")
        Base.metadata.create_all(bind=engine)
        logger.info("✓ Tables created/verified")
        
        # Migrate existing data
        logger.info("Migrating existing services data...")
        
        with get_db_context() as db:
            # Get all servers with services_to_monitor data
            servers = db.query(ServerModel).filter(
                ServerModel.services_to_monitor.isnot(None)
            ).all()
            
            migrated_count = 0
            skipped_count = 0
            
            for server in servers:
                if server.services_to_monitor and isinstance(server.services_to_monitor, list):
                    logger.info(f"Migrating services for server: {server.server_name}")
                    
                    for service_name in server.services_to_monitor:
                        if not service_name or not service_name.strip():
                            continue
                        
                        # Check if service already exists
                        existing = db.query(MonitoredServiceModel).filter(
                            MonitoredServiceModel.server_id == server.server_id,
                            MonitoredServiceModel.service_name == service_name.strip()
                        ).first()
                        
                        if not existing:
                            # Create new monitored service
                            monitored_service = MonitoredServiceModel(
                                server_id=server.server_id,
                                service_name=service_name.strip()
                            )
                            db.add(monitored_service)
                            migrated_count += 1
                            logger.info(f"  ✓ Added service: {service_name}")
                        else:
                            skipped_count += 1
                            logger.info(f"  - Skipped existing service: {service_name}")
            
            db.commit()
            
            logger.info(f"✓ Migration completed!")
            logger.info(f"  - Migrated services: {migrated_count}")
            logger.info(f"  - Skipped (already exists): {skipped_count}")
            logger.info(f"  - Servers processed: {len(servers)}")
        
        print("\n" + "="*60)
        print("DATABASE MIGRATION SUCCESSFUL")
        print("="*60)
        print(f"✓ Tables created/verified")
        print(f"✓ Migrated {migrated_count} services from {len(servers)} servers")
        print(f"✓ Skipped {skipped_count} duplicate services")
        print("\nNote: services_to_monitor column is kept for backward compatibility")
        print("      but is now deprecated. Use MonitoredService table instead.")
        print("="*60 + "\n")
        
        return True
    
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        print(f"\n❌ Migration failed: {e}\n")
        return False


def verify_migration():
    """Verify the migration was successful."""
    try:
        with get_db_context() as db:
            # Check if monitored_services table exists and has data
            service_count = db.query(MonitoredServiceModel).count()
            server_count = db.query(ServerModel).count()
            
            print("\n" + "="*60)
            print("MIGRATION VERIFICATION")
            print("="*60)
            print(f"Total servers: {server_count}")
            print(f"Total monitored services: {service_count}")
            
            # Show sample data
            if service_count > 0:
                print("\nSample monitored services:")
                samples = db.query(MonitoredServiceModel).limit(10).all()
                for svc in samples:
                    server = db.query(ServerModel).filter(
                        ServerModel.server_id == svc.server_id
                    ).first()
                    print(f"  - {server.server_name}: {svc.service_name}")
            
            print("="*60 + "\n")
            return True
    
    except Exception as e:
        print(f"\n❌ Verification failed: {e}\n")
        return False


if __name__ == "__main__":
    print("\n" + "="*60)
    print("DATABASE MIGRATION SCRIPT")
    print("Adding MonitoredService table and migrating existing data")
    print("="*60 + "\n")
    
    # Perform migration
    success = migrate_database()
    
    if success:
        # Verify migration
        verify_migration()
        print("✓ Migration and verification completed successfully!\n")
        sys.exit(0)
    else:
        print("❌ Migration failed. Please check the logs.\n")
        sys.exit(1)
