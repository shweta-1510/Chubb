"""
Database connectivity health check collector.
"""
import time
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.models.health_check_result import DatabaseStatus, HealthStatus
from app.models.database_config import DatabaseConfig
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseCollector:
    """Collects database connectivity health metrics."""
    
    def __init__(self, db_config: DatabaseConfig):
        """
        Initialize database collector.
        
        Args:
            db_config: Database configuration
        """
        self.db_config = db_config
        self.engine = None
    
    def check_connectivity(self) -> DatabaseStatus:
        """
        Check database connectivity and measure response time.
        
        Returns:
            DatabaseStatus object with connectivity results
        """
        start_time = time.time()
        
        try:
            # Create engine with connection timeout
            self.engine = create_engine(
                self.db_config.connection_string,
                pool_pre_ping=True,
                connect_args={'connect_timeout': 10}
            )
            
            # Execute simple validation query
            with self.engine.connect() as connection:
                result = connection.execute(text("SELECT 1"))
                result.fetchone()
            
            # Calculate response time
            response_time_ms = (time.time() - start_time) * 1000
            
            logger.info(
                f"Database connection successful: {self.db_config.database_type} "
                f"at {self.db_config.host}:{self.db_config.port} "
                f"({response_time_ms:.2f}ms)"
            )
            
            return DatabaseStatus(
                database_type=self.db_config.database_type,
                host=self.db_config.host,
                port=self.db_config.port,
                is_connected=True,
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time_ms,
                error_message=None
            )
            
        except SQLAlchemyError as e:
            response_time_ms = (time.time() - start_time) * 1000
            error_message = str(e)
            
            logger.error(
                f"Database connection failed: {self.db_config.database_type} "
                f"at {self.db_config.host}:{self.db_config.port} - {error_message}"
            )
            
            return DatabaseStatus(
                database_type=self.db_config.database_type,
                host=self.db_config.host,
                port=self.db_config.port,
                is_connected=False,
                status=HealthStatus.CRITICAL,
                response_time_ms=response_time_ms,
                error_message=error_message
            )
            
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            error_message = f"Unexpected error: {str(e)}"
            
            logger.error(
                f"Unexpected error during database check: {self.db_config.database_type} "
                f"at {self.db_config.host}:{self.db_config.port} - {error_message}"
            )
            
            return DatabaseStatus(
                database_type=self.db_config.database_type,
                host=self.db_config.host,
                port=self.db_config.port,
                is_connected=False,
                status=HealthStatus.FAILED,
                response_time_ms=response_time_ms,
                error_message=error_message
            )
        
        finally:
            # Cleanup engine
            if self.engine:
                self.engine.dispose()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.engine:
            self.engine.dispose()
