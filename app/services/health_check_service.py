"""
Health check service orchestration layer.
Coordinates collection, evaluation, and reporting of health checks.
"""
import time
from typing import List, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.models.server import ServerModel
from app.models.monitored_service import MonitoredServiceModel
from app.models.health_check_result import HealthCheckResult, HealthStatus, ServiceStatus
from app.models.health_check_history import HealthCheckHistoryModel
from app.models.database_config import DatabaseConfig
from app.collectors.linux_collector import LinuxCollector
from app.collectors.windows_collector import WindowsCollector
from app.collectors.database_collector import DatabaseCollector
from app.utils.threshold import ThresholdEvaluator
from app.utils.logger import get_logger
from app.database.db import get_db_context, get_db_read_context
from app.config import config

logger = get_logger(__name__)


class HealthCheckService:
    """
    Orchestrates health check execution across servers.
    Implements the Service Layer pattern.
    """

    def __init__(self):
        self.threshold_evaluator = ThresholdEvaluator()

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

            result = HealthCheckResult(
                server_id=server.server_id,
                server_name=server.server_name,
                ip_address=server.ip_address,
                hostname=server.hostname,
                os_type=server.os_type,
                environment=server.environment,
                execution_time=datetime.now()
            )

            # Load monitored services BEFORE opening SSH/WinRM connection
            # to avoid nested DB sessions
            monitored_service_names = self._load_monitored_services(server.server_id)

            if server.os_type.lower() == 'linux':
                self._check_linux_server(server, result, monitored_service_names)
            elif server.os_type.lower() == 'windows':
                self._check_windows_server(server, result, monitored_service_names)
            else:
                result.error_message = f"Unsupported OS type: {server.os_type}"
                result.overall_status = HealthStatus.FAILED
                return result

            if server.database_type and server.database_host and server.database_port:
                self._check_database_connectivity(server, result)

            result.overall_status = result.calculate_overall_status()
            result.duration_seconds = time.time() - start_time

            logger.info(
                f"Health check completed for {server.server_name}: "
                f"Status={result.overall_status.value}, Duration={result.duration_seconds:.2f}s"
            )

            # Persist result to history
            self._save_history(result)

            return result

        except Exception as e:
            logger.error(f"Error during health check for {server.server_name}: {e}")
            duration = time.time() - start_time

            result = HealthCheckResult(
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
            self._save_history(result)
            return result

    def _load_monitored_services(self, server_id: int) -> List[str]:
        """Load monitored service names from DB before opening remote connections."""
        try:
            with get_db_read_context() as db:
                services = db.query(MonitoredServiceModel).filter(
                    MonitoredServiceModel.server_id == server_id
                ).all()
                return [s.service_name for s in services]
        except Exception as e:
            logger.error(f"Error loading monitored services for server {server_id}: {e}")
            return []

    def _check_linux_server(self, server: ServerModel, result: HealthCheckResult,
                             service_names: List[str]) -> None:
        """
        Execute Linux server health checks using a single SSH connection.
        Reuses the same connection for metrics AND service checks.
        """
        try:
            with LinuxCollector(
                hostname=server.ip_address,
                username=server.username,
                password=server.credential_reference,
                port=22
            ) as collector:

                cpu_usage = collector.get_cpu_usage()
                if cpu_usage is not None:
                    result.cpu_metric = self.threshold_evaluator.evaluate_cpu(cpu_usage)

                memory_usage = collector.get_memory_usage()
                if memory_usage is not None:
                    result.memory_metric = self.threshold_evaluator.evaluate_memory(memory_usage)

                disk_usage = collector.get_disk_usage()
                if disk_usage is not None:
                    result.disk_metric = self.threshold_evaluator.evaluate_disk(disk_usage)

                # Reuse the same SSH connection for all service checks
                if service_names:
                    result.service_statuses = collector.check_services(service_names)

        except Exception as e:
            logger.error(f"Error checking Linux server {server.server_name}: {e}")
            result.error_message = f"Linux check error: {str(e)}"

    def _check_windows_server(self, server: ServerModel, result: HealthCheckResult,
                               service_names: List[str]) -> None:
        """
        Execute Windows server health checks using a single WinRM connection.
        Reuses the same connection for metrics AND service checks.
        """
        try:
            with WindowsCollector(
                hostname=server.ip_address,
                username=server.username,
                password=server.credential_reference,
                port=5985
            ) as collector:

                cpu_usage = collector.get_cpu_usage()
                if cpu_usage is not None:
                    result.cpu_metric = self.threshold_evaluator.evaluate_cpu(cpu_usage)

                memory_usage = collector.get_memory_usage()
                if memory_usage is not None:
                    result.memory_metric = self.threshold_evaluator.evaluate_memory(memory_usage)

                disk_usage = collector.get_disk_usage()
                if disk_usage is not None:
                    result.disk_metric = self.threshold_evaluator.evaluate_disk(disk_usage)

                if service_names:
                    result.service_statuses = collector.check_services(service_names)

        except Exception as e:
            logger.error(f"Error checking Windows server {server.server_name}: {e}")
            result.error_message = f"Windows check error: {str(e)}"

    def _check_database_connectivity(self, server: ServerModel, result: HealthCheckResult) -> None:
        """Check database connectivity."""
        try:
            db_config = DatabaseConfig(
                database_type=server.database_type,
                host=server.database_host,
                port=server.database_port,
                username=server.username,
                password=server.credential_reference,
                database_name='postgres'
            )
            with DatabaseCollector(db_config) as collector:
                result.database_status = collector.check_connectivity()
        except Exception as e:
            logger.error(f"Error checking database for {server.server_name}: {e}")

    def _save_history(self, result: HealthCheckResult) -> None:
        """Persist health check result to history table."""
        try:
            with get_db_context() as db:
                history = HealthCheckHistoryModel(
                    server_id=result.server_id,
                    server_name=result.server_name,
                    overall_status=result.overall_status.value,
                    cpu_usage=result.cpu_metric.usage if result.cpu_metric else None,
                    cpu_status=result.cpu_metric.status.value if result.cpu_metric else None,
                    memory_usage=result.memory_metric.usage if result.memory_metric else None,
                    memory_status=result.memory_metric.status.value if result.memory_metric else None,
                    disk_usage=result.disk_metric.usage if result.disk_metric else None,
                    disk_status=result.disk_metric.status.value if result.disk_metric else None,
                    duration_seconds=result.duration_seconds,
                    error_message=result.error_message,
                    details_json=result.to_dict()
                )
                db.add(history)
        except Exception as e:
            logger.error(f"Failed to save health check history for {result.server_name}: {e}")

    def execute_batch_health_check(self, servers: List[ServerModel]) -> List[HealthCheckResult]:
        """
        Execute health checks for multiple servers in parallel.

        Args:
            servers: List of server models to check

        Returns:
            List of HealthCheckResults
        """
        active_servers = [s for s in servers if s.is_active]

        if not active_servers:
            return []

        results = []
        max_workers = min(config.max_workers, len(active_servers))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_server = {
                executor.submit(self.execute_health_check, server): server
                for server in active_servers
            }

            for future in as_completed(future_to_server):
                server = future_to_server[future]
                try:
                    results.append(future.result())
                except Exception as e:
                    logger.error(f"Unexpected error for {server.server_name}: {e}")

        # Sort results to match original server order
        server_order = {s.server_id: i for i, s in enumerate(active_servers)}
        results.sort(key=lambda r: server_order.get(r.server_id, 999))

        return results
