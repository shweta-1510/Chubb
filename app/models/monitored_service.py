"""
Monitored Service model for database.
Represents services to be monitored for each server.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import Dict, Any

from app.database.db import Base


class MonitoredServiceModel(Base):
    """
    Monitored Services table model.
    Stores services to be monitored for each server.
    """
    __tablename__ = "monitored_services"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    server_id = Column(Integer, ForeignKey('server_management.server_id', ondelete='CASCADE'), nullable=False, index=True)
    service_name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Add unique constraint to prevent duplicate services for same server
    __table_args__ = (
        UniqueConstraint('server_id', 'service_name', name='uix_server_service'),
    )
    
    # Relationship to server
    server = relationship("ServerModel", back_populates="monitored_services")

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "server_id": self.server_id,
            "service_name": self.service_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<MonitoredService(id={self.id}, server_id={self.server_id}, service={self.service_name})>"
