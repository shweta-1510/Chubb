"""
Linux server health check collector using SSH/Paramiko.
"""
import re
from typing import Optional, List, Tuple
import paramiko
from paramiko import SSHClient, AutoAddPolicy

from app.models.health_check_result import ServiceStatus, HealthStatus
from app.utils.logger import get_logger
from app.utils.retry import retry
from app.config import config
from app.utils.ssh_auth import build_ssh_connect_kwargs

logger = get_logger(__name__)


class LinuxCollector:
    """Collects health metrics from Linux servers via SSH."""
    
    def __init__(self, hostname: str, username: str, password: Optional[str] = None, 
                 key_filename: Optional[str] = None, port: int = 22):
        """
        Initialize Linux collector.
        
        Args:
            hostname: Server hostname or IP address
            username: SSH username
            password: SSH password (optional if using key)
            key_filename: Path to private key file (optional)
            port: SSH port (default: 22)
        """
        self.hostname = hostname
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.port = port
        self.client: Optional[SSHClient] = None
    
    @retry(max_attempts=3, delay=2.0, exceptions=(Exception,))
    def connect(self) -> bool:
        """
        Establish SSH connection with retry on transient failures.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(AutoAddPolicy())

            credential_reference = self.key_filename or self.password
            connect_kwargs = build_ssh_connect_kwargs(
                hostname=self.hostname,
                username=self.username,
                credential_reference=credential_reference,
                port=self.port,
                timeout=config.ssh.timeout,
            )
            
            self.client.connect(**connect_kwargs)
            logger.info(f"Successfully connected to {self.hostname}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to {self.hostname}: {e}")
            return False
    
    def disconnect(self) -> None:
        """Close SSH connection."""
        if self.client:
            self.client.close()
            logger.info(f"Disconnected from {self.hostname}")
    
    def execute_command(self, command: str) -> Tuple[str, str, int]:
        """
        Execute command on remote server.
        
        Args:
            command: Command to execute
            
        Returns:
            Tuple of (stdout, stderr, exit_code)
        """
        try:
            stdin, stdout, stderr = self.client.exec_command(command)
            exit_code = stdout.channel.recv_exit_status()
            
            stdout_str = stdout.read().decode('utf-8').strip()
            stderr_str = stderr.read().decode('utf-8').strip()
            
            return stdout_str, stderr_str, exit_code
            
        except Exception as e:
            logger.error(f"Error executing command '{command}': {e}")
            return "", str(e), -1
    
    def get_cpu_usage(self) -> Optional[float]:
        """
        Get CPU utilization percentage.
        
        Returns:
            CPU usage percentage or None if failed
        """
        try:
            # Use top command to get CPU usage
            command = "top -bn1 | grep 'Cpu(s)' | sed 's/.*, *\\([0-9.]*\\)%* id.*/\\1/' | awk '{print 100 - $1}'"
            stdout, stderr, exit_code = self.execute_command(command)
            
            if exit_code == 0 and stdout:
                return float(stdout)
            else:
                logger.warning(f"Failed to get CPU usage: {stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting CPU usage: {e}")
            return None
    
    def get_memory_usage(self) -> Optional[float]:
        """
        Get memory utilization percentage.
        
        Returns:
            Memory usage percentage or None if failed
        """
        try:
            # Use free command to get memory usage
            command = "free | grep Mem | awk '{print ($3/$2) * 100.0}'"
            stdout, stderr, exit_code = self.execute_command(command)
            
            if exit_code == 0 and stdout:
                return float(stdout)
            else:
                logger.warning(f"Failed to get memory usage: {stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting memory usage: {e}")
            return None
    
    def get_disk_usage(self) -> Optional[float]:
        """
        Get disk utilization percentage for root filesystem.
        
        Returns:
            Disk usage percentage or None if failed
        """
        try:
            # Use df command to get disk usage
            command = "df -h / | tail -1 | awk '{print $5}' | sed 's/%//'"
            stdout, stderr, exit_code = self.execute_command(command)
            
            if exit_code == 0 and stdout:
                return float(stdout)
            else:
                logger.warning(f"Failed to get disk usage: {stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting disk usage: {e}")
            return None
    
    def check_service_status(self, service_name: str) -> ServiceStatus:
        """
        Check status of a systemd service.
        
        Args:
            service_name: Name of the service to check
            
        Returns:
            ServiceStatus object
        """
        try:
            # Validate service name to prevent command injection
            if not re.match(r'^[a-zA-Z0-9_\-@.]+$', service_name):
                return ServiceStatus(
                    service_name=service_name,
                    status=HealthStatus.FAILED,
                    is_running=False,
                    message="Invalid service name"
                )
            
            # Check if service is active using systemctl
            command = f"systemctl is-active {service_name}"
            stdout, stderr, exit_code = self.execute_command(command)
            
            is_running = (exit_code == 0 and stdout.lower() == "active")
            
            status = HealthStatus.HEALTHY if is_running else HealthStatus.CRITICAL
            message = "Service is running" if is_running else "Service is not running"
            
            return ServiceStatus(
                service_name=service_name,
                status=status,
                is_running=is_running,
                message=message
            )
            
        except Exception as e:
            logger.error(f"Error checking service {service_name}: {e}")
            return ServiceStatus(
                service_name=service_name,
                status=HealthStatus.FAILED,
                is_running=False,
                message=f"Error: {str(e)}"
            )
    
    def check_services(self, services: List[str]) -> List[ServiceStatus]:
        """
        Check status of multiple services.
        
        Args:
            services: List of service names to check
            
        Returns:
            List of ServiceStatus objects
        """
        results = []
        for service in services:
            results.append(self.check_service_status(service))
        return results
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
