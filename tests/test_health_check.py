"""
Example test file for Health Check Service.
Run with: pytest tests/
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from app.models.server import ServerModel
from app.models.health_check_result import (
    HealthCheckResult, 
    HealthStatus,
    ResourceMetric,
    ServiceStatus
)
from app.services.health_check_service import HealthCheckService
from app.utils.threshold import ThresholdEvaluator


class TestThresholdEvaluator:
    """Test threshold evaluation logic."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.evaluator = ThresholdEvaluator()
    
    def test_cpu_healthy(self):
        """Test CPU evaluation - healthy status."""
        result = self.evaluator.evaluate_cpu(50.0)
        assert result.usage == 50.0
        assert result.status == HealthStatus.HEALTHY
    
    def test_cpu_warning(self):
        """Test CPU evaluation - warning status."""
        result = self.evaluator.evaluate_cpu(80.0)
        assert result.usage == 80.0
        assert result.status == HealthStatus.WARNING
    
    def test_cpu_critical(self):
        """Test CPU evaluation - critical status."""
        result = self.evaluator.evaluate_cpu(95.0)
        assert result.usage == 95.0
        assert result.status == HealthStatus.CRITICAL
    
    def test_memory_thresholds(self):
        """Test memory evaluation at different thresholds."""
        # Healthy
        result = self.evaluator.evaluate_memory(60.0)
        assert result.status == HealthStatus.HEALTHY
        
        # Warning
        result = self.evaluator.evaluate_memory(80.0)
        assert result.status == HealthStatus.WARNING
        
        # Critical
        result = self.evaluator.evaluate_memory(92.0)
        assert result.status == HealthStatus.CRITICAL
    
    def test_disk_thresholds(self):
        """Test disk evaluation at different thresholds."""
        # Healthy
        result = self.evaluator.evaluate_disk(50.0)
        assert result.status == HealthStatus.HEALTHY
        
        # Warning
        result = self.evaluator.evaluate_disk(75.0)
        assert result.status == HealthStatus.WARNING
        
        # Critical
        result = self.evaluator.evaluate_disk(85.0)
        assert result.status == HealthStatus.CRITICAL


class TestHealthCheckResult:
    """Test health check result model."""
    
    def test_calculate_overall_status_healthy(self):
        """Test overall status calculation - all healthy."""
        result = HealthCheckResult(
            server_id=1,
            server_name="test-server",
            ip_address="192.168.1.100",
            hostname="test",
            os_type="Linux",
            environment="Production",
            cpu_metric=ResourceMetric(usage=50.0, status=HealthStatus.HEALTHY),
            memory_metric=ResourceMetric(usage=60.0, status=HealthStatus.HEALTHY),
            disk_metric=ResourceMetric(usage=40.0, status=HealthStatus.HEALTHY)
        )
        
        overall = result.calculate_overall_status()
        assert overall == HealthStatus.HEALTHY
    
    def test_calculate_overall_status_critical(self):
        """Test overall status calculation - has critical."""
        result = HealthCheckResult(
            server_id=1,
            server_name="test-server",
            ip_address="192.168.1.100",
            hostname="test",
            os_type="Linux",
            environment="Production",
            cpu_metric=ResourceMetric(usage=95.0, status=HealthStatus.CRITICAL),
            memory_metric=ResourceMetric(usage=60.0, status=HealthStatus.HEALTHY),
            disk_metric=ResourceMetric(usage=40.0, status=HealthStatus.HEALTHY)
        )
        
        overall = result.calculate_overall_status()
        assert overall == HealthStatus.CRITICAL
    
    def test_calculate_overall_status_warning(self):
        """Test overall status calculation - has warning."""
        result = HealthCheckResult(
            server_id=1,
            server_name="test-server",
            ip_address="192.168.1.100",
            hostname="test",
            os_type="Linux",
            environment="Production",
            cpu_metric=ResourceMetric(usage=80.0, status=HealthStatus.WARNING),
            memory_metric=ResourceMetric(usage=60.0, status=HealthStatus.HEALTHY),
            disk_metric=ResourceMetric(usage=40.0, status=HealthStatus.HEALTHY)
        )
        
        overall = result.calculate_overall_status()
        assert overall == HealthStatus.WARNING
    
    def test_to_dict_serialization(self):
        """Test result serialization to dictionary."""
        result = HealthCheckResult(
            server_id=1,
            server_name="test-server",
            ip_address="192.168.1.100",
            hostname="test",
            os_type="Linux",
            environment="Production",
            cpu_metric=ResourceMetric(usage=50.0, status=HealthStatus.HEALTHY)
        )
        
        result_dict = result.to_dict()
        
        assert result_dict['server_id'] == 1
        assert result_dict['server_name'] == "test-server"
        assert result_dict['ip_address'] == "192.168.1.100"
        assert result_dict['cpu_metric']['usage'] == 50.0
        assert result_dict['cpu_metric']['status'] == "Healthy"


class TestServiceStatus:
    """Test service status model."""
    
    def test_service_running(self):
        """Test service status - running."""
        status = ServiceStatus(
            service_name="nginx",
            status=HealthStatus.HEALTHY,
            is_running=True,
            message="Service is running"
        )
        
        assert status.service_name == "nginx"
        assert status.is_running is True
        assert status.status == HealthStatus.HEALTHY
    
    def test_service_stopped(self):
        """Test service status - stopped."""
        status = ServiceStatus(
            service_name="apache2",
            status=HealthStatus.CRITICAL,
            is_running=False,
            message="Service is not running"
        )
        
        assert status.service_name == "apache2"
        assert status.is_running is False
        assert status.status == HealthStatus.CRITICAL


@pytest.fixture
def mock_server():
    """Create a mock server model."""
    return ServerModel(
        server_id=1,
        server_name="test-server",
        ip_address="192.168.1.100",
        hostname="test",
        os_type="Linux",
        environment="Production",
        connection_type="SSH",
        username="admin",
        credential_reference="password123",
        services_to_monitor=["nginx", "postgresql"],
        is_active=True
    )


class TestHealthCheckService:
    """Test health check service."""
    
    def test_service_initialization(self):
        """Test service initialization."""
        service = HealthCheckService()
        assert service.threshold_evaluator is not None
    
    @patch('app.services.health_check_service.LinuxCollector')
    def test_execute_health_check_linux(self, mock_linux_collector, mock_server):
        """Test health check execution for Linux server."""
        # Mock collector methods
        mock_collector = Mock()
        mock_collector.get_cpu_usage.return_value = 50.0
        mock_collector.get_memory_usage.return_value = 60.0
        mock_collector.get_disk_usage.return_value = 40.0
        mock_collector.check_services.return_value = [
            ServiceStatus(
                service_name="nginx",
                status=HealthStatus.HEALTHY,
                is_running=True,
                message="Running"
            )
        ]
        
        mock_linux_collector.return_value.__enter__.return_value = mock_collector
        
        # Execute health check
        service = HealthCheckService()
        result = service.execute_health_check(mock_server)
        
        # Assertions
        assert result.server_name == "test-server"
        assert result.cpu_metric is not None
        assert result.cpu_metric.usage == 50.0
        assert result.memory_metric.usage == 60.0
        assert result.disk_metric.usage == 40.0
        assert len(result.service_statuses) == 1
        assert result.overall_status == HealthStatus.HEALTHY


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
