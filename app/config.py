"""
Configuration module for Health Monitor Application.
Manages database connections and application settings.
"""
import os
from typing import Optional
from urllib.parse import quote_plus
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class DatabaseConfig(BaseModel):
    """Database configuration settings."""
    host: str = Field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    port: int = Field(default_factory=lambda: int(os.getenv("DB_PORT", "5432")))
    username: str = Field(default_factory=lambda: os.getenv("DB_USERNAME", "postgres"))
    password: str = Field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))
    database: str = Field(default_factory=lambda: os.getenv("DB_NAME", "health_monitor"))
    
    @property
    def connection_string(self) -> str:
        """Generate SQLAlchemy connection string with URL-encoded password."""
        # URL-encode password to handle special characters like @, #, etc.
        encoded_password = quote_plus(self.password)
        return f"postgresql://{self.username}:{encoded_password}@{self.host}:{self.port}/{self.database}"


class SSHConfig(BaseModel):
    """SSH connection configuration."""
    timeout: int = Field(default=30, description="SSH connection timeout in seconds")
    port: int = Field(default=22, description="Default SSH port")


class WinRMConfig(BaseModel):
    """WinRM connection configuration."""
    timeout: int = Field(default=30, description="WinRM connection timeout in seconds")
    port: int = Field(default=5985, description="Default WinRM HTTP port")
    secure_port: int = Field(default=5986, description="Default WinRM HTTPS port")


class ThresholdConfig(BaseModel):
    """Resource utilization threshold configuration."""
    cpu_critical: float = Field(default=90.0, description="CPU critical threshold percentage")
    cpu_warning: float = Field(default=75.0, description="CPU warning threshold percentage")
    memory_critical: float = Field(default=90.0, description="Memory critical threshold percentage")
    memory_warning: float = Field(default=75.0, description="Memory warning threshold percentage")
    disk_critical: float = Field(default=80.0, description="Disk critical threshold percentage")
    disk_warning: float = Field(default=70.0, description="Disk warning threshold percentage")


class ApplicationConfig(BaseModel):
    """Main application configuration."""
    app_name: str = "Environment Health Check Monitor"
    version: str = "1.0.0"
    debug: bool = Field(default_factory=lambda: os.getenv("DEBUG", "False").lower() == "true")
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    max_workers: int = Field(default_factory=lambda: int(os.getenv("MAX_WORKERS", "5")))
    
    # Component configurations
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    ssh: SSHConfig = Field(default_factory=SSHConfig)
    winrm: WinRMConfig = Field(default_factory=WinRMConfig)
    thresholds: ThresholdConfig = Field(default_factory=ThresholdConfig)


# Global configuration instance
config = ApplicationConfig()
