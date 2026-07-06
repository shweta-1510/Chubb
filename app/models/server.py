"""
Server model for database.
Represents server configuration and connection details.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.database.db import Base


class ServerModel(Base):
    """
    Server management table model.
    Stores server configuration and connection details.
    """
    __tablename__ = "server_management"

    server_id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    server_name = Column(String(255), nullable=False, unique=True, index=True)
    ip_address = Column(String(45), nullable=False)  # Support IPv4 and IPv6
    hostname = Column(String(255), nullable=True)
    os_type = Column(String(50), nullable=False)  # Linux/Windows
    environment = Column(String(50), nullable=True)  # Dev/Staging/Production
    cloud_provider = Column(String(50), nullable=True)  # AWS/Azure/GCP/OnPrem
    connection_type = Column(String(50), nullable=False)  # SSH/WinRM
    username = Column(String(100), nullable=False)
    credential_reference = Column(String(255), nullable=True)  # Reference to credential store
    # services_to_monitor column deprecated - use MonitoredService table instead
    services_to_monitor = Column(JSON, nullable=True)  # DEPRECATED: Use monitored_services relationship
    database_type = Column(String(50), nullable=True)  # PostgreSQL/MySQL/MSSQL
    database_host = Column(String(255), nullable=True)
    database_port = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationship to monitored services
    monitored_services = relationship("MonitoredServiceModel", back_populates="server", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "server_id": self.server_id,
            "server_name": self.server_name,
            "ip_address": self.ip_address,
            "hostname": self.hostname,
            "os_type": self.os_type,
            "environment": self.environment,
            "cloud_provider": self.cloud_provider,
            "connection_type": self.connection_type,
            "username": self.username,
            "credential_reference": self.credential_reference,
            "services_to_monitor": self.services_to_monitor,
            "database_type": self.database_type,
            "database_host": self.database_host,
            "database_port": self.database_port,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<Server(id={self.server_id}, name={self.server_name}, ip={self.ip_address})>"
