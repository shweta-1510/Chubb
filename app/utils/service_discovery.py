"""
Service Discovery utility for discovering available services on servers.
"""
import paramiko
import winrm
import socket
import re
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from app.utils.logger import get_logger
from app.models.server import ServerModel
from app.utils.ssh_auth import build_ssh_connect_kwargs

logger = get_logger(__name__)


class ServiceDiscovery:
    """Service discovery for Linux and Windows servers."""
    
    def __init__(self):
        self.timeout = 30
        self.banner_timeout = 10  # Shorter timeout for SSH banner
    
    def _test_port_connectivity(self, host: str, port: int, timeout: int = 5) -> Tuple[bool, Optional[str]]:
        """
        Test if a port is reachable on the target host.
        
        Args:
            host: Hostname or IP address
            port: Port number to test
            timeout: Connection timeout in seconds
            
        Returns:
            Tuple of (is_reachable, error_message)
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                return True, None
            else:
                return False, f"Port {port} is not reachable (connection refused)"
        
        except socket.gaierror:
            return False, f"Cannot resolve hostname: {host}"
        except socket.timeout:
            return False, f"Connection timeout to {host}:{port}"
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"
    
    def discover_services(self, server: ServerModel) -> Tuple[bool, List[str], Optional[str]]:
        """
        Discover all available services on a server.
        
        Args:
            server: ServerModel instance with connection details
            
        Returns:
            Tuple of (success, services_list, error_message)
        """
        try:
            if server.os_type == "Linux":
                return self._discover_linux_services(server)
            elif server.os_type == "Windows":
                return self._discover_windows_services(server)
            else:
                return False, [], f"Unsupported OS type: {server.os_type}"
        
        except Exception as e:
            logger.error(f"Service discovery error for {server.server_name}: {e}")
            return False, [], str(e)
    
    def _discover_linux_services(self, server: ServerModel) -> Tuple[bool, List[str], Optional[str]]:
        """
        Discover services on Linux server using SSH.
        
        Args:
            server: ServerModel instance
            
        Returns:
            Tuple of (success, services_list, error_message)
        """
        ssh_client = None
        
        try:
            # Step 1: Test basic connectivity first
            logger.info(f"Testing connectivity to {server.server_name} ({server.ip_address}:22)")
            is_reachable, conn_error = self._test_port_connectivity(server.ip_address, 22, timeout=5)
            
            if not is_reachable:
                error_msg = f"Cannot reach server on port 22 (SSH). {conn_error}\n\n" \
                           f"Please verify:\n" \
                           f"  • Server IP address is correct: {server.ip_address}\n" \
                           f"  • Server is powered on and reachable\n" \
                           f"  • SSH service is running on the server\n" \
                           f"  • Firewall allows SSH connections (port 22)\n" \
                           f"  • Network connectivity from this machine"
                logger.error(f"Port connectivity test failed for {server.server_name}: {conn_error}")
                return False, [], error_msg
            
            logger.info(f"Port 22 is reachable on {server.server_name}")
            
            # Step 2: Create SSH client
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Determine authentication method
            try:
                connect_kwargs = build_ssh_connect_kwargs(
                    hostname=server.ip_address,
                    username=server.username,
                    credential_reference=server.credential_reference,
                    port=22,
                    timeout=self.timeout,
                    banner_timeout=self.banner_timeout,
                    auth_timeout=self.timeout,
                )
                if connect_kwargs.get('pkey') is not None:
                    logger.info(
                        f"Using key file authentication for {server.server_name}: {server.credential_reference}"
                    )
                elif server.credential_reference:
                    logger.info(f"Using password authentication for {server.server_name}")
            except ValueError as e:
                logger.error(f"Failed to load SSH key for {server.server_name}: {e}")
                return False, [], f"SSH key error: {e}"
            
            # Step 3: Connect to server
            logger.info(f"Establishing SSH connection to {server.server_name}")
            logger.debug(f"Connection parameters: hostname={server.ip_address}, username={server.username}, port=22")
            ssh_client.connect(**connect_kwargs)
            logger.info(f"SSH connection established successfully for {server.server_name}")
            
            # Step 4: Discover services
            # Try systemctl list-unit-files first
            command = "systemctl list-unit-files --type=service --no-pager --no-legend"
            logger.info(f"Running service discovery command on {server.server_name}")
            stdin, stdout, stderr = ssh_client.exec_command(command, timeout=self.timeout)
            
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            
            services = set()
            
            if output:
                # Parse systemctl list-unit-files output
                # Format: service_name.service  enabled/disabled/static
                for line in output.strip().split('\n'):
                    if line.strip():
                        parts = line.split()
                        if parts and parts[0].endswith('.service'):
                            service_name = parts[0].replace('.service', '')
                            services.add(service_name)
            
            # If no services found, try alternative command
            if not services:
                logger.info(f"No services found with list-unit-files, trying list-units on {server.server_name}")
                command = "systemctl list-units --type=service --all --no-pager --no-legend"
                stdin, stdout, stderr = ssh_client.exec_command(command, timeout=self.timeout)
                output = stdout.read().decode('utf-8')
                
                for line in output.strip().split('\n'):
                    if line.strip():
                        parts = line.split()
                        if parts and parts[0].endswith('.service'):
                            service_name = parts[0].replace('.service', '')
                            services.add(service_name)
            
            # Sort services alphabetically
            sorted_services = sorted(list(services))
            
            if sorted_services:
                logger.info(f"Discovered {len(sorted_services)} services on {server.server_name}")
                return True, sorted_services, None
            else:
                error_msg = "No services discovered on server. The server may not be using systemd."
                logger.warning(f"{error_msg} - Server: {server.server_name}")
                return False, [], error_msg
        
        except paramiko.AuthenticationException as e:
            error_msg = f"Authentication failed.\n\n" \
                       f"Please verify:\n" \
                       f"  • Username is correct: {server.username}\n" \
                       f"  • Credential file is valid and has correct permissions\n" \
                       f"  • Key file format is supported (PPK/PEM/OpenSSH)\n" \
                       f"  • User has SSH access to the server\n\n" \
                       f"Error: {str(e)}"
            logger.error(f"Authentication failed for {server.server_name}: {e}")
            return False, [], error_msg
        
        except paramiko.SSHException as e:
            error_str = str(e)
            
            # Provide specific guidance for common SSH errors
            if "banner" in error_str.lower():
                error_msg = f"SSH protocol error: Cannot establish SSH session.\n\n" \
                           f"This usually means:\n" \
                           f"  • The IP address doesn't point to an SSH server\n" \
                           f"  • Wrong port (verify it's port 22 for SSH)\n" \
                           f"  • Network device (router/firewall) is blocking SSH\n" \
                           f"  • Server SSH service is not properly configured\n\n" \
                           f"Troubleshooting steps:\n" \
                           f"  1. Verify server IP: {server.ip_address}\n" \
                           f"  2. Test SSH manually: ssh {server.username}@{server.ip_address}\n" \
                           f"  3. Check if SSH is running: systemctl status sshd\n" \
                           f"  4. Verify firewall rules allow SSH (port 22)\n\n" \
                           f"Technical error: {error_str}"
            elif "key" in error_str.lower():
                error_msg = f"SSH key error: {error_str}\n\n" \
                           f"Please verify:\n" \
                           f"  • Key file exists: {server.credential_reference}\n" \
                           f"  • Key file format is correct (PPK/PEM/OpenSSH)\n" \
                           f"  • Key file has proper permissions (readable)\n" \
                           f"  • Public key is authorized on the server"
            else:
                error_msg = f"SSH connection error: {error_str}\n\n" \
                           f"Please check:\n" \
                           f"  • Server is reachable: {server.ip_address}\n" \
                           f"  • SSH service is running on the server\n" \
                           f"  • Network/firewall allows SSH connections"
            
            logger.error(f"SSH error for {server.server_name}: {e}")
            return False, [], error_msg
        
        except socket.timeout:
            error_msg = f"Connection timeout.\n\n" \
                       f"The server took too long to respond. Please check:\n" \
                       f"  • Server is powered on and reachable\n" \
                       f"  • Network latency is acceptable\n" \
                       f"  • Firewall is not dropping packets\n" \
                       f"  • Server is not overloaded"
            logger.error(f"Timeout connecting to {server.server_name}")
            return False, [], error_msg
        
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}\n\n" \
                       f"Please verify:\n" \
                       f"  • Server configuration is correct\n" \
                       f"  • All required information is provided\n" \
                       f"  • Check application logs for details"
            logger.error(f"Unexpected error for {server.server_name}: {e}", exc_info=True)
            return False, [], error_msg
        
        finally:
            if ssh_client:
                try:
                    ssh_client.close()
                    logger.info(f"SSH connection closed for {server.server_name}")
                except:
                    pass
    
    def _discover_windows_services(self, server: ServerModel) -> Tuple[bool, List[str], Optional[str]]:
        """
        Discover services on Windows server using WinRM.
        
        Args:
            server: ServerModel instance
            
        Returns:
            Tuple of (success, services_list, error_message)
        """
        session = None
        
        try:
            # Test basic connectivity first
            logger.info(f"Testing connectivity to {server.server_name} ({server.ip_address}:5985)")
            is_reachable, conn_error = self._test_port_connectivity(server.ip_address, 5985, timeout=5)
            
            if not is_reachable:
                error_msg = f"Cannot reach server on port 5985 (WinRM). {conn_error}\n\n" \
                           f"Please verify:\n" \
                           f"  • Server IP address is correct: {server.ip_address}\n" \
                           f"  • Server is powered on and reachable\n" \
                           f"  • WinRM service is enabled on the server\n" \
                           f"  • Firewall allows WinRM connections (port 5985)\n" \
                           f"  • WinRM is configured: winrm quickconfig"
                logger.error(f"Port connectivity test failed for {server.server_name}: {conn_error}")
                return False, [], error_msg
            
            logger.info(f"Port 5985 is reachable on {server.server_name}")
            
            # Create WinRM session
            endpoint = f"http://{server.ip_address}:5985/wsman"
            
            logger.info(f"Establishing WinRM connection to {server.server_name}")
            
            session = winrm.Session(
                endpoint,
                auth=(server.username, server.credential_reference),
                transport='ntlm',
                server_cert_validation='ignore'
            )
            
            # PowerShell command to get all services
            ps_command = "Get-Service | Select-Object -ExpandProperty Name"
            
            logger.info(f"Running service discovery command on {server.server_name}")
            result = session.run_ps(ps_command)
            
            if result.status_code == 0:
                output = result.std_out.decode('utf-8')
                
                services = set()
                for line in output.strip().split('\n'):
                    service_name = line.strip()
                    if service_name:
                        services.add(service_name)
                
                # Sort services alphabetically
                sorted_services = sorted(list(services))
                
                if sorted_services:
                    logger.info(f"Discovered {len(sorted_services)} services on {server.server_name}")
                    return True, sorted_services, None
                else:
                    return False, [], "No services discovered on server"
            else:
                error = result.std_err.decode('utf-8')
                error_msg = f"Service discovery command failed: {error}\n\n" \
                           f"Please verify:\n" \
                           f"  • User has permissions to query services\n" \
                           f"  • PowerShell is available on the server"
                logger.error(f"Service discovery failed for {server.server_name}: {error}")
                return False, [], error_msg
        
        except winrm.exceptions.InvalidCredentialsError as e:
            error_msg = f"Authentication failed.\n\n" \
                       f"Please verify:\n" \
                       f"  • Username is correct: {server.username}\n" \
                       f"  • Password is correct\n" \
                       f"  • User has remote access permissions\n" \
                       f"  • User is in Remote Management Users group\n\n" \
                       f"Error: {str(e)}"
            logger.error(f"Authentication failed for {server.server_name}: {e}")
            return False, [], error_msg
        
        except Exception as e:
            error_str = str(e)
            error_msg = f"WinRM connection error: {error_str}\n\n" \
                       f"Please verify:\n" \
                       f"  • WinRM is enabled: Enable-PSRemoting -Force\n" \
                       f"  • Firewall allows WinRM (port 5985/5986)\n" \
                       f"  • Server is reachable: {server.ip_address}\n" \
                       f"  • Network connectivity is working"
            logger.error(f"WinRM error for {server.server_name}: {e}")
            return False, [], error_msg
    
    def check_service_status(self, server: ServerModel, service_name: str) -> Tuple[bool, str, str]:
        """
        Check the status of a specific service.
        
        Args:
            server: ServerModel instance
            service_name: Name of the service to check
            
        Returns:
            Tuple of (success, status, error_message)
            status can be: 'active', 'inactive', 'failed', 'running', 'stopped'
        """
        try:
            if server.os_type == "Linux":
                return self._check_linux_service_status(server, service_name)
            elif server.os_type == "Windows":
                return self._check_windows_service_status(server, service_name)
            else:
                return False, "unknown", f"Unsupported OS type: {server.os_type}"
        
        except Exception as e:
            logger.error(f"Service status check error for {service_name} on {server.server_name}: {e}")
            return False, "unknown", str(e)
    
    def _check_linux_service_status(self, server: ServerModel, service_name: str) -> Tuple[bool, str, str]:
        """Check service status on Linux using systemctl is-active."""
        # Validate service name to prevent command injection
        if not re.match(r'^[a-zA-Z0-9_\-@.]+$', service_name):
            return False, "unknown", f"Invalid service name: {service_name}"
        
        ssh_client = None
        
        try:
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            try:
                connect_kwargs = build_ssh_connect_kwargs(
                    hostname=server.ip_address,
                    username=server.username,
                    credential_reference=server.credential_reference,
                    port=22,
                    timeout=self.timeout,
                )
            except ValueError as e:
                return False, "unknown", f"SSH key error: {e}"
            
            ssh_client.connect(**connect_kwargs)
            
            # Use systemctl is-active to check service status
            command = f"systemctl is-active {service_name}"
            stdin, stdout, stderr = ssh_client.exec_command(command, timeout=self.timeout)
            
            status = stdout.read().decode('utf-8').strip()
            
            # Possible values: active, inactive, failed, activating, deactivating, unknown
            return True, status, None
        
        except Exception as e:
            return False, "unknown", str(e)
        
        finally:
            if ssh_client:
                ssh_client.close()
    
    def _check_windows_service_status(self, server: ServerModel, service_name: str) -> Tuple[bool, str, str]:
        """Check service status on Windows using PowerShell."""
        try:
            endpoint = f"http://{server.ip_address}:5985/wsman"
            
            session = winrm.Session(
                endpoint,
                auth=(server.username, server.credential_reference),
                transport='ntlm',
                server_cert_validation='ignore'
            )
            
            # PowerShell command to get service status
            ps_command = f"(Get-Service -Name '{service_name}').Status"
            
            result = session.run_ps(ps_command)
            
            if result.status_code == 0:
                status = result.std_out.decode('utf-8').strip().lower()
                # Windows statuses: Running, Stopped, Paused, etc.
                # Map to: active, inactive
                if status == 'running':
                    return True, 'active', None
                else:
                    return True, 'inactive', None
            else:
                return False, "unknown", result.std_err.decode('utf-8')
        
        except Exception as e:
            return False, "unknown", str(e)
