"""
Logging configuration for the application.
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from app.config import config


class Logger:
    """Centralized logging configuration."""
    
    _instance: Optional[logging.Logger] = None
    
    @classmethod
    def get_logger(cls, name: str = __name__) -> logging.Logger:
        """
        Get or create application logger.
        
        Args:
            name: Logger name
            
        Returns:
            Configured logger instance
        """
        if cls._instance is None:
            cls._setup_logging()
        
        return logging.getLogger(name)
    
    @classmethod
    def _setup_logging(cls) -> None:
        """Setup logging configuration."""
        # Create logs directory
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, config.log_level.upper()))
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG if config.debug else logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # File handler
        log_file = log_dir / f"health_monitor_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        cls._instance = root_logger
        
        # Log initial message
        root_logger.info(f"Logging initialized - Level: {config.log_level}")


# Convenience function
def get_logger(name: str = __name__) -> logging.Logger:
    """Get logger instance."""
    return Logger.get_logger(name)
