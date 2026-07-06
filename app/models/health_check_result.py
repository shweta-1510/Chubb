"""
Health check result data models.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class HealthStatus(str, Enum):
    """Health status enumeration."""
    HEALTHY = "Healthy"
    WARNING = "Warning"
    CRITICAL = "Critical"
    UNKNOWN = "Unknown"
    FAILED = "Failed"


@dataclass
class ResourceMetric:
    """Resource utilization metric."""
    usage: float
    status: HealthStatus
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "usage": round(self.usage, 2),
            "status": self.status.value,
            "threshold_warning": self.threshold_warning,
            "threshold_critical": self.threshold_critical,
        }


@dataclass
class ServiceStatus:
    """Service status information."""
    service_name: str
    status: HealthStatus
    is_running: bool
    message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "status": self.status.value,
            "is_running": self.is_running,
            "message": self.message,
        }


@dataclass
class DatabaseStatus:
    """Database connectivity status."""
    database_type: str
    host: str
    port: int
    is_connected: bool
    status: HealthStatus
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "database_type": self.database_type,
            "host": self.host,
            "port": self.port,
            "is_connected": self.is_connected,
            "status": self.status.value,
            "response_time_ms": round(response_time_ms, 2) if (response_time_ms := self.response_time_ms) else None,
            "error_message": self.error_message,
        }


@dataclass
class HealthCheckResult:
    """
    Complete health check result for a server.
    """
    server_id: int
    server_name: str
    ip_address: str
    hostname: Optional[str]
    os_type: str
    environment: Optional[str]
    
    # Resource metrics
    cpu_metric: Optional[ResourceMetric] = None
    memory_metric: Optional[ResourceMetric] = None
    disk_metric: Optional[ResourceMetric] = None
    
    # Service statuses
    service_statuses: List[ServiceStatus] = field(default_factory=list)
    
    # Database status
    database_status: Optional[DatabaseStatus] = None
    
    # Overall status
    overall_status: HealthStatus = HealthStatus.UNKNOWN
    
    # Metadata
    execution_time: datetime = field(default_factory=datetime.now)
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "server_id": self.server_id,
            "server_name": self.server_name,
            "ip_address": self.ip_address,
            "hostname": self.hostname,
            "os_type": self.os_type,
            "environment": self.environment,
            "cpu_metric": self.cpu_metric.to_dict() if self.cpu_metric else None,
            "memory_metric": self.memory_metric.to_dict() if self.memory_metric else None,
            "disk_metric": self.disk_metric.to_dict() if self.disk_metric else None,
            "service_statuses": [s.to_dict() for s in self.service_statuses],
            "database_status": self.database_status.to_dict() if self.database_status else None,
            "overall_status": self.overall_status.value,
            "execution_time": self.execution_time.isoformat(),
            "duration_seconds": round(self.duration_seconds, 2) if self.duration_seconds else None,
            "error_message": self.error_message,
        }
    
    def calculate_overall_status(self) -> HealthStatus:
        """Calculate overall health status based on all metrics."""
        statuses = []
        
        if self.cpu_metric:
            statuses.append(self.cpu_metric.status)
        if self.memory_metric:
            statuses.append(self.memory_metric.status)
        if self.disk_metric:
            statuses.append(self.disk_metric.status)
        if self.database_status:
            statuses.append(self.database_status.status)
        
        for service in self.service_statuses:
            statuses.append(service.status)
        
        # Priority: CRITICAL > WARNING > FAILED > HEALTHY > UNKNOWN
        if HealthStatus.CRITICAL in statuses:
            return HealthStatus.CRITICAL
        elif HealthStatus.WARNING in statuses:
            return HealthStatus.WARNING
        elif HealthStatus.FAILED in statuses:
            return HealthStatus.FAILED
        elif HealthStatus.HEALTHY in statuses:
            return HealthStatus.HEALTHY
        else:
            return HealthStatus.UNKNOWN
