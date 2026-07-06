"""
Health check service orchestration layer.
Coordinates collection, evaluation, and reporting of health checks.
"""
import time
from typing import List, Optional
from datetime import datetime

from app.models.server import ServerModel
from app.models.monitored_service import MonitoredServiceModel
from app.models.health_check_result import HealthCheckResult, HealthStatus, ServiceStatus
from app.models.database_config import DatabaseConfig
from app.collectors.linux_collector import LinuxCollector
from app.collectors.windows_collector import WindowsCollector
from app.collectors.database_collector import DatabaseCollector
from app.utils.threshold import ThresholdEvaluator
from app.utils.service_discovery import ServiceDiscovery
from app.utils.logger import get_logger
from app.database.db import get_db_context

logger = get_logger(__name__)


class HealthCheckService:
    """
    Orchestrates health check execution across servers.
    Implements the Service Layer pattern.
    """
    
    def __init__(self):
        self.threshold_evaluator = ThresholdEvaluator()
        self.service_discovery = ServiceDiscovery()
    
    def execute_health_check(self, server: ServerModel) -> HealthCheckResult:
        """
        Execute health check for a single server.
        
        Args:
            server: Server model to check
            
        Returns:
            HealthCheckResult with metrics and status
        """
        start_time = time.time()
        
        try:
            logger.info(f"Starting health check for server: {server.server_name} ({server.ip_address})")
            
            # Initialize result
            result = HealthCheckResult(
                server_id=server.server_id,
                server_name=server.server_name,
                ip_address=server.ip_address,
                hostname=server.hostname,
                os_type=server.os_type,
                environment=server.environment,
                execution_time=datetime.now()
            )
            
            # Execute OS-specific checks
            if server.os_type.lower() == 'linux':
                self._check_linux_server(server, result)
            elif server.os_type.lower() == 'windows':
                self._check_windows_server(server, result)
            else:
                result.error_message = f"Unsupported OS type: {server.os_type}"
                result.overall_status = HealthStatus.FAILED
                return result
            
            # Check database connectivity if configured
            if server.database_type and server.database_host and server.database_port:
                self._check_database_connectivity(server, result)
            
            # Calculate overall status
            result.overall_status = result.calculate_overall_status()
            
            # Calculate duration
            result.duration_seconds = time.time() - start_time
            
            logger.info(
                f"Health check completed for {server.server_name}: "
                f"Status={result.overall_status.value}, Duration={result.duration_seconds:.2f}s"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error during health check for {server.server_name}: {e}")
            duration = time.time() - start_time
            
            return HealthCheckResult(
                server_id=server.server_id,
                server_name=server.server_name,
                ip_address=server.ip_address,
                hostname=server.hostname,
                os_type=server.os_type,
                environment=server.environment,
                execution_time=datetime.now(),
                overall_status=HealthStatus.FAILED,
                error_message=str(e),
                duration_seconds=duration
            )
    
    def _check_linux_server(self, server: ServerModel, result: HealthCheckResult) -> None:
        """
        Execute Linux server health checks.
        
        Args:
            server: Server model
            result: HealthCheckResult to populate
        """
        try:
            with LinuxCollector(
                hostname=server.ip_address,
                username=server.username,
                password=server.credential_reference,  # In production, fetch from secure store
                port=22
            ) as collector:
                
                # Collect CPU usage
                cpu_usage = collector.get_cpu_usage()
                if cpu_usage is not None:
                    result.cpu_metric = self.threshold_evaluator.evaluate_cpu(cpu_usage)
                
                # Collect memory usage
                memory_usage = collector.get_memory_usage()
                if memory_usage is not None:
                    result.memory_metric = self.threshold_evaluator.evaluate_memory(memory_usage)
                
                # Collect disk usage
                disk_usage = collector.get_disk_usage()
                if disk_usage is not None:
                    result.disk_metric = self.threshold_evaluator.evaluate_disk(disk_usage)
                
                # Check monitored services from database
                self._check_monitored_services(server, result)
                
        except Exception as e:
            logger.error(f"Error checking Linux server {server.server_name}: {e}")
            result.error_message = f"Linux check error: {str(e)}"
    
    def _check_windows_server(self, server: ServerModel, result: HealthCheckResult) -> None:
        """
        Execute Windows server health checks.
        
        Args:
            server: Server model
            result: HealthCheckResult to populate
        """
        try:
            with WindowsCollector(
                hostname=server.ip_address,
                username=server.username,
                password=server.credential_reference,  # In production, fetch from secure store
                port=5985
            ) as collector:
                
                # Collect CPU usage
                cpu_usage = collector.get_cpu_usage()
                if cpu_usage is not None:
                    result.cpu_metric = self.threshold_evaluator.evaluate_cpu(cpu_usage)
                
                # Collect memory usage
                memory_usage = collector.get_memory_usage()
                if memory_usage is not None:
                    result.memory_metric = self.threshold_evaluator.evaluate_memory(memory_usage)
                
                # Collect disk usage
                disk_usage = collector.get_disk_usage()
                if disk_usage is not None:
                    result.disk_metric = self.threshold_evaluator.evaluate_disk(disk_usage)
                
                # Check monitored services from database
                self._check_monitored_services(server, result)
                
        except Exception as e:
            logger.error(f"Error checking Windows server {server.server_name}: {e}")
            result.error_message = f"Windows check error: {str(e)}"
    
    def _check_monitored_services(self, server: ServerModel, result: HealthCheckResult) -> None:
        """
        Check status of monitored services from database.
        
        Args:
            server: Server model
            result: HealthCheckResult to populate
        """
        try:
            # Get monitored services from database
            with get_db_context() as db:
                monitored_services = db.query(MonitoredServiceModel).filter(
                    MonitoredServiceModel.server_id == server.server_id
                ).all()
                
                if not monitored_services:
                    logger.info(f"No monitored services configured for {server.server_name}")
                    return
                
                service_statuses = []
                
                for monitored_service in monitored_services:
                    service_name = monitored_service.service_name
                    
                    # Check service status using service discovery utility
                    success, status, error_msg = self.service_discovery.check_service_status(
                        server, service_name
                    )
                    
                    if success:
                        # Map status to is_running boolean
                        # active = running, anything else = not running
                        is_running = (status.lower() == 'active')
                        
                        # Determine health status based on threshold rules:
                        # Running/Active = Healthy, Stopped/Inactive/Failed = Critical
                        health_status = HealthStatus.HEALTHY if is_running else HealthStatus.CRITICAL
                        
                        service_status = ServiceStatus(
                            service_name=service_name,
                            is_running=is_running,
                            status=health_status
                        )
                        
                        service_statuses.append(service_status)
                        
                        logger.info(f"Service {service_name} on {server.server_name}: {status} -> {health_status.value}")
                    else:
                        # Failed to check service status
                        logger.error(f"Failed to check service {service_name} on {server.server_name}: {error_msg}")
                        
                        service_status = ServiceStatus(
                            service_name=service_name,
                            is_running=False,
                            status=HealthStatus.CRITICAL
                        )
                        service_statuses.append(service_status)
                
                result.service_statuses = service_statuses
                
        except Exception as e:
            logger.error(f"Error checking monitored services for {server.server_name}: {e}")
    
    def _check_database_connectivity(self, server: ServerModel, result: HealthCheckResult) -> None:
        """
        Check database connectivity.
        
        Args:
            server: Server model
            result: HealthCheckResult to populate
        """
        try:
            db_config = DatabaseConfig(
                database_type=server.database_type,
                host=server.database_host,
                port=server.database_port,
                username=server.username,
                password=server.credential_reference,  # In production, fetch from secure store
                database_name='postgres'  # Default database for connectivity check
            )
            
            with DatabaseCollector(db_config) as collector:
                result.database_status = collector.check_connectivity()
                
        except Exception as e:
            logger.error(f"Error checking database for {server.server_name}: {e}")
    
    def execute_batch_health_check(self, servers: List[ServerModel]) -> List[HealthCheckResult]:
        """
        Execute health checks for multiple servers.
        
        Args:
            servers: List of server models to check
            
        Returns:
            List of HealthCheckResults
        """
        results = []
        
        for server in servers:
            if not server.is_active:
                logger.info(f"Skipping inactive server: {server.server_name}")
                continue
            
            result = self.execute_health_check(server)
            results.append(result)
        
        return results
