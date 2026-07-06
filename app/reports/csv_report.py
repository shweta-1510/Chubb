"""
CSV report generator using Pandas.
"""
from typing import List
import pandas as pd
from pathlib import Path

from app.models.health_check_result import HealthCheckResult
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CSVReportGenerator:
    """Generates CSV health check reports."""
    
    def generate(self, results: List[HealthCheckResult], output_file: str = None) -> str:
        """
        Generate CSV report from health check results.
        
        Args:
            results: List of health check results
            output_file: Optional output file path
            
        Returns:
            CSV content as string
        """
        try:
            # Flatten health check results into tabular format
            rows = []
            
            for result in results:
                base_row = {
                    'Server ID': result.server_id,
                    'Server Name': result.server_name,
                    'IP Address': result.ip_address,
                    'Hostname': result.hostname or 'N/A',
                    'OS Type': result.os_type,
                    'Environment': result.environment or 'N/A',
                    'CPU Usage (%)': result.cpu_metric.usage if result.cpu_metric else None,
                    'CPU Status': result.cpu_metric.status.value if result.cpu_metric else 'N/A',
                    'Memory Usage (%)': result.memory_metric.usage if result.memory_metric else None,
                    'Memory Status': result.memory_metric.status.value if result.memory_metric else 'N/A',
                    'Disk Usage (%)': result.disk_metric.usage if result.disk_metric else None,
                    'Disk Status': result.disk_metric.status.value if result.disk_metric else 'N/A',
                    'Overall Status': result.overall_status.value,
                    'Execution Time': result.execution_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'Duration (seconds)': result.duration_seconds,
                }
                
                # Add service statuses
                if result.service_statuses:
                    service_names = ', '.join([s.service_name for s in result.service_statuses])
                    service_statuses = ', '.join([s.status.value for s in result.service_statuses])
                    base_row['Services'] = service_names
                    base_row['Service Statuses'] = service_statuses
                else:
                    base_row['Services'] = 'N/A'
                    base_row['Service Statuses'] = 'N/A'
                
                # Add database status
                if result.database_status:
                    base_row['Database Type'] = result.database_status.database_type
                    base_row['Database Host'] = result.database_status.host
                    base_row['Database Connected'] = 'Yes' if result.database_status.is_connected else 'No'
                    base_row['Database Status'] = result.database_status.status.value
                else:
                    base_row['Database Type'] = 'N/A'
                    base_row['Database Host'] = 'N/A'
                    base_row['Database Connected'] = 'N/A'
                    base_row['Database Status'] = 'N/A'
                
                # Add error message if any
                base_row['Error Message'] = result.error_message or 'N/A'
                
                rows.append(base_row)
            
            # Create DataFrame
            df = pd.DataFrame(rows)
            
            # Generate CSV content
            csv_content = df.to_csv(index=False)
            
            # Save to file if specified
            if output_file:
                output_path = Path(output_file)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                df.to_csv(output_path, index=False)
                logger.info(f"CSV report saved to {output_file}")
            
            return csv_content
            
        except Exception as e:
            logger.error(f"Error generating CSV report: {e}")
            raise
