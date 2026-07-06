"""
Windows server health check collector using WinRM.
"""
import re
from typing import Optional, List
import winrm
from winrm.protocol import Protocol

from app.models.health_check_result import ServiceStatus, HealthStatus
from app.utils.logger import get_logger
from app.config import config

logger = get_logger(__name__)


class WindowsCollector:
    """Collects health metrics from Windows servers via WinRM."""
    
    def __init__(self, hostname: str, username: str, password: str, 
                 port: int = 5985, use_https: bool = False):
        """
        Initialize Windows collector.
        
        Args:
            hostname: Server hostname or IP address
            username: Windows username
            password: Windows password
            port: WinRM port (default: 5985 for HTTP, 5986 for HTTPS)
            use_https: Use HTTPS connection
        """
        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = port
        self.use_https = use_https
        self.session: Optional[Protocol] = None
        
        # Build endpoint URL
        protocol = "https" if use_https else "http"
        self.endpoint = f"{protocol}://{hostname}:{port}/wsman"
    
    def connect(self) -> bool:
        """
        Establish WinRM connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.session = winrm.Session(
                self.endpoint,
                auth=(self.username, self.password),
                server_cert_validation='ignore' if self.use_https else None
            )
            
            # Test connection
            result = self.session.run_cmd('echo', ['test'])
            if result.status_code == 0:
                logger.info(f"Successfully connected to {self.hostname}")
                return True
            else:
                logger.error(f"Connection test failed: {result.std_err.decode()}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to {self.hostname}: {e}")
            return False
    
    def execute_command(self, command: str, use_powershell: bool = True) -> tuple:
        """
        Execute command on remote Windows server.
        
        Args:
            command: Command to execute
            use_powershell: Use PowerShell (default) or cmd
            
        Returns:
            Tuple of (stdout, stderr, exit_code)
        """
        try:
            if use_powershell:
                result = self.session.run_ps(command)
            else:
                result = self.session.run_cmd(command)
            
            stdout = result.std_out.decode('utf-8').strip()
            stderr = result.std_err.decode('utf-8').strip()
            exit_code = result.status_code
            
            return stdout, stderr, exit_code
            
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
            # PowerShell command to get CPU usage
            command = """
            $cpu = Get-Counter '\\Processor(_Total)\\% Processor Time' -SampleInterval 1 -MaxSamples 1
            $cpu.CounterSamples[0].CookedValue
            """
            stdout, stderr, exit_code = self.execute_command(command)
            
            if exit_code == 0 and stdout:
                return float(stdout.strip())
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
            # PowerShell command to get memory usage
            command = """
            $os = Get-CimInstance Win32_OperatingSystem
            $total = $os.TotalVisibleMemorySize
            $free = $os.FreePhysicalMemory
            $used = $total - $free
            $percentage = ($used / $total) * 100
            $percentage
            """
            stdout, stderr, exit_code = self.execute_command(command)
            
            if exit_code == 0 and stdout:
                return float(stdout.strip())
            else:
                logger.warning(f"Failed to get memory usage: {stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting memory usage: {e}")
            return None
    
    def get_disk_usage(self) -> Optional[float]:
        """
        Get disk utilization percentage for C: drive.
        
        Returns:
            Disk usage percentage or None if failed
        """
        try:
            # PowerShell command to get disk usage
            command = """
            $disk = Get-PSDrive C
            $used = $disk.Used
            $total = $used + $disk.Free
            $percentage = ($used / $total) * 100
            $percentage
            """
            stdout, stderr, exit_code = self.execute_command(command)
            
            if exit_code == 0 and stdout:
                return float(stdout.strip())
            else:
                logger.warning(f"Failed to get disk usage: {stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting disk usage: {e}")
            return None
    
    def check_service_status(self, service_name: str) -> ServiceStatus:
        """
        Check status of a Windows service.
        
        Args:
            service_name: Name of the service to check
            
        Returns:
            ServiceStatus object
        """
        try:
            # PowerShell command to check service status
            command = f"(Get-Service -Name '{service_name}').Status"
            stdout, stderr, exit_code = self.execute_command(command)
            
            if exit_code == 0 and stdout:
                service_status = stdout.strip().lower()
                is_running = (service_status == "running")
                
                status = HealthStatus.HEALTHY if is_running else HealthStatus.CRITICAL
                message = f"Service is {service_status}"
                
                return ServiceStatus(
                    service_name=service_name,
                    status=status,
                    is_running=is_running,
                    message=message
                )
            else:
                return ServiceStatus(
                    service_name=service_name,
                    status=HealthStatus.FAILED,
                    is_running=False,
                    message=f"Service not found or error: {stderr}"
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
        # WinRM session doesn't need explicit cleanup
        pass
