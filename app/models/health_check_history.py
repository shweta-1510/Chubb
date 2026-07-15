"""
Health check history model for persisting results to the database.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from typing import Dict, Any

from app.database.db import Base


class HealthCheckHistoryModel(Base):
    """Stores historical health check results per server."""
    __tablename__ = "health_check_history"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    server_id = Column(Integer, ForeignKey("server_management.server_id", ondelete="CASCADE"), nullable=False, index=True)
    server_name = Column(String(255), nullable=False)
    overall_status = Column(String(50), nullable=False)
    cpu_usage = Column(Float, nullable=True)
    cpu_status = Column(String(50), nullable=True)
    memory_usage = Column(Float, nullable=True)
    memory_status = Column(String(50), nullable=True)
    disk_usage = Column(Float, nullable=True)
    disk_status = Column(String(50), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    details_json = Column(JSON, nullable=True)  # Full result as JSON for reporting
    executed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    server = relationship("ServerModel")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "server_id": self.server_id,
            "server_name": self.server_name,
            "overall_status": self.overall_status,
            "cpu_usage": self.cpu_usage,
            "cpu_status": self.cpu_status,
            "memory_usage": self.memory_usage,
            "memory_status": self.memory_status,
            "disk_usage": self.disk_usage,
            "disk_status": self.disk_status,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
        }

    def __repr__(self) -> str:
        return f"<HealthCheckHistory(id={self.id}, server={self.server_name}, status={self.overall_status})>"
