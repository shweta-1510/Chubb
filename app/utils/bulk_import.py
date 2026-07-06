"""
Utility for bulk importing server data from various file formats.
Supports CSV, XLSX, and YAML formats.
"""
import pandas as pd
import yaml
from typing import List, Dict, Any, Optional
from io import StringIO, BytesIO
import json

from app.utils.logger import get_logger

logger = get_logger(__name__)


class BulkImportValidator:
    """Validates bulk import data."""
    
    REQUIRED_FIELDS = ["server_name", "ip_address", "os_type", "connection_type", "username", "credential_reference"]
    VALID_OS_TYPES = ["Linux", "Windows"]
    VALID_CONNECTION_TYPES = ["SSH", "WinRM"]
    VALID_ENVIRONMENTS = ["Development", "Staging", "UAT", "Production", "DR"]
    VALID_CLOUD_PROVIDERS = ["AWS", "Azure", "GCP", "On-Premise", "Other"]
    VALID_DATABASE_TYPES = ["PostgreSQL", "MySQL", "MSSQL", "None"]
    
    @staticmethod
    def validate_server_data(server_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate a single server entry.
        
        Args:
            server_data: Dictionary containing server information
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields
        for field in BulkImportValidator.REQUIRED_FIELDS:
            if field not in server_data or not server_data[field]:
                return False, f"Missing required field: {field}"
        
        # Validate os_type
        if server_data["os_type"] not in BulkImportValidator.VALID_OS_TYPES:
            return False, f"Invalid os_type: {server_data['os_type']}. Must be one of {BulkImportValidator.VALID_OS_TYPES}"
        
        # Validate connection_type
        if server_data["connection_type"] not in BulkImportValidator.VALID_CONNECTION_TYPES:
            return False, f"Invalid connection_type: {server_data['connection_type']}. Must be one of {BulkImportValidator.VALID_CONNECTION_TYPES}"
        
        # Validate optional fields if present
        if "environment" in server_data and server_data["environment"]:
            if server_data["environment"] not in BulkImportValidator.VALID_ENVIRONMENTS:
                return False, f"Invalid environment: {server_data['environment']}"
        
        if "cloud_provider" in server_data and server_data["cloud_provider"]:
            if server_data["cloud_provider"] not in BulkImportValidator.VALID_CLOUD_PROVIDERS:
                return False, f"Invalid cloud_provider: {server_data['cloud_provider']}"
        
        if "database_type" in server_data and server_data["database_type"]:
            if server_data["database_type"] not in BulkImportValidator.VALID_DATABASE_TYPES:
                return False, f"Invalid database_type: {server_data['database_type']}"
        
        # Validate services_to_monitor format
        if "services_to_monitor" in server_data and server_data["services_to_monitor"]:
            services = server_data["services_to_monitor"]
            if isinstance(services, str):
                # Convert comma-separated string to list
                server_data["services_to_monitor"] = [s.strip() for s in services.split(",") if s.strip()]
            elif not isinstance(services, list):
                return False, "services_to_monitor must be a list or comma-separated string"
        
        return True, None


class BulkImportParser:
    """Parses bulk import files in different formats."""
    
    @staticmethod
    def parse_csv(file_content: bytes) -> List[Dict[str, Any]]:
        """
        Parse CSV file content.
        
        Args:
            file_content: Raw CSV file bytes
            
        Returns:
            List of server dictionaries
        """
        try:
            df = pd.read_csv(BytesIO(file_content))
            return BulkImportParser._dataframe_to_servers(df)
        except Exception as e:
            logger.error(f"Error parsing CSV: {e}")
            raise ValueError(f"Failed to parse CSV file: {str(e)}")
    
    @staticmethod
    def parse_xlsx(file_content: bytes) -> List[Dict[str, Any]]:
        """
        Parse XLSX file content.
        
        Args:
            file_content: Raw XLSX file bytes
            
        Returns:
            List of server dictionaries
        """
        try:
            df = pd.read_excel(BytesIO(file_content), engine='openpyxl')
            return BulkImportParser._dataframe_to_servers(df)
        except Exception as e:
            logger.error(f"Error parsing XLSX: {e}")
            raise ValueError(f"Failed to parse XLSX file: {str(e)}")
    
    @staticmethod
    def parse_yaml(file_content: bytes) -> List[Dict[str, Any]]:
        """
        Parse YAML file content.
        
        Args:
            file_content: Raw YAML file bytes
            
        Returns:
            List of server dictionaries
        """
        try:
            content = file_content.decode('utf-8')
            data = yaml.safe_load(content)
            
            # Handle different YAML structures
            if isinstance(data, list):
                # List of servers directly
                return data
            elif isinstance(data, dict) and 'servers' in data:
                # Servers under 'servers' key
                return data['servers']
            else:
                raise ValueError("YAML must contain a list of servers or a 'servers' key with a list")
                
        except Exception as e:
            logger.error(f"Error parsing YAML: {e}")
            raise ValueError(f"Failed to parse YAML file: {str(e)}")
    
    @staticmethod
    def _dataframe_to_servers(df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Convert pandas DataFrame to list of server dictionaries.
        
        Args:
            df: Pandas DataFrame
            
        Returns:
            List of server dictionaries
        """
        # Replace NaN with None
        df = df.where(pd.notna(df), None)
        
        # Convert to list of dictionaries
        servers = df.to_dict('records')
        
        # Clean up the data
        for server in servers:
            # Remove None values from optional fields
            server = {k: v for k, v in server.items() if v is not None}
            
            # Convert is_active to boolean if present
            if 'is_active' in server:
                server['is_active'] = bool(server['is_active'])
        
        return servers


class BulkImportService:
    """Service for handling bulk import operations."""
    
    def __init__(self):
        self.parser = BulkImportParser()
        self.validator = BulkImportValidator()
    
    def process_import_file(self, file_content: bytes, file_type: str) -> tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
        """
        Process an import file and return validated server data.
        
        Args:
            file_content: Raw file content bytes
            file_type: File type ('csv', 'xlsx', or 'yaml')
            
        Returns:
            Tuple of (valid_servers, errors) where errors is a list of error dictionaries
        """
        # Parse file based on type
        if file_type == 'csv':
            servers = self.parser.parse_csv(file_content)
        elif file_type == 'xlsx':
            servers = self.parser.parse_xlsx(file_content)
        elif file_type == 'yaml':
            servers = self.parser.parse_yaml(file_content)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
        
        # Validate each server
        valid_servers = []
        errors = []
        
        for idx, server_data in enumerate(servers, start=1):
            is_valid, error_msg = self.validator.validate_server_data(server_data)
            
            if is_valid:
                # Set defaults for optional fields
                server_data.setdefault('is_active', True)
                server_data.setdefault('hostname', None)
                server_data.setdefault('environment', None)
                server_data.setdefault('cloud_provider', None)
                server_data.setdefault('services_to_monitor', None)
                server_data.setdefault('database_type', None)
                server_data.setdefault('database_host', None)
                server_data.setdefault('database_port', None)
                
                valid_servers.append(server_data)
            else:
                errors.append({
                    'row': idx,
                    'server_name': server_data.get('server_name', 'Unknown'),
                    'error': error_msg
                })
        
        return valid_servers, errors
    
    def generate_template_csv(self) -> str:
        """Generate a CSV template for bulk import."""
        headers = [
            "server_name",
            "ip_address",
            "hostname",
            "os_type",
            "environment",
            "cloud_provider",
            "connection_type",
            "username",
            "credential_reference",
            "services_to_monitor",
            "database_type",
            "database_host",
            "database_port",
            "is_active"
        ]
        
        example_row = [
            "web-server-01",
            "192.168.1.10",
            "webserver01.example.com",
            "Linux",
            "Production",
            "AWS",
            "SSH",
            "admin",
            "path/to/key.ppk",
            "nginx,redis,postgresql",
            "PostgreSQL",
            "localhost",
            "5432",
            "True"
        ]
        
        df = pd.DataFrame([headers, example_row])
        return df.to_csv(index=False, header=False)
    
    def generate_template_yaml(self) -> str:
        """Generate a YAML template for bulk import."""
        template = {
            'servers': [
                {
                    'server_name': 'web-server-01',
                    'ip_address': '192.168.1.10',
                    'hostname': 'webserver01.example.com',
                    'os_type': 'Linux',
                    'environment': 'Production',
                    'cloud_provider': 'AWS',
                    'connection_type': 'SSH',
                    'username': 'admin',
                    'credential_reference': 'path/to/key.ppk',
                    'services_to_monitor': ['nginx', 'redis', 'postgresql'],
                    'database_type': 'PostgreSQL',
                    'database_host': 'localhost',
                    'database_port': 5432,
                    'is_active': True
                }
            ]
        }
        
        return yaml.dump(template, default_flow_style=False, sort_keys=False)
