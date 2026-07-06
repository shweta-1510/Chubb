"""
HTML report generator using Jinja2 templates.
"""
from typing import List
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path

from app.models.health_check_result import HealthCheckResult, HealthStatus
from app.utils.logger import get_logger

logger = get_logger(__name__)


class HTMLReportGenerator:
    """Generates HTML health check reports."""
    
    def __init__(self, template_dir: str = "templates"):
        """
        Initialize HTML report generator.
        
        Args:
            template_dir: Directory containing Jinja2 templates
        """
        self.template_dir = Path(template_dir)
        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
        # Add custom filters
        self.env.filters['format_percentage'] = self._format_percentage
        self.env.filters['status_color'] = self._status_color
        self.env.filters['status_badge_class'] = self._status_badge_class
    
    @staticmethod
    def _format_percentage(value: float) -> str:
        """Format percentage value."""
        if value is None:
            return "N/A"
        return f"{value:.2f}%"
    
    @staticmethod
    def _status_color(status: str) -> str:
        """Get color for status."""
        color_map = {
            HealthStatus.HEALTHY.value: "#28a745",  # Green
            HealthStatus.WARNING.value: "#ffc107",  # Yellow
            HealthStatus.CRITICAL.value: "#dc3545",  # Red
            HealthStatus.FAILED.value: "#6c757d",   # Gray
            HealthStatus.UNKNOWN.value: "#17a2b8",  # Blue
        }
        return color_map.get(status, "#6c757d")
    
    @staticmethod
    def _status_badge_class(status: str) -> str:
        """Get Bootstrap badge class for status."""
        class_map = {
            HealthStatus.HEALTHY.value: "badge-success",
            HealthStatus.WARNING.value: "badge-warning",
            HealthStatus.CRITICAL.value: "badge-danger",
            HealthStatus.FAILED.value: "badge-secondary",
            HealthStatus.UNKNOWN.value: "badge-info",
        }
        return class_map.get(status, "badge-secondary")
    
    def generate(self, results: List[HealthCheckResult], output_file: str = None) -> str:
        """
        Generate HTML report from health check results.
        
        Args:
            results: List of health check results
            output_file: Optional output file path
            
        Returns:
            HTML content as string
        """
        try:
            template = self.env.get_template('health_report.html')
            
            # Prepare data for template
            report_data = {
                'title': 'Environment Health Check Report',
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'total_servers': len(results),
                'healthy_count': sum(1 for r in results if r.overall_status == HealthStatus.HEALTHY),
                'warning_count': sum(1 for r in results if r.overall_status == HealthStatus.WARNING),
                'critical_count': sum(1 for r in results if r.overall_status == HealthStatus.CRITICAL),
                'results': [r.to_dict() for r in results]
            }
            
            html_content = template.render(**report_data)
            
            # Save to file if specified
            if output_file:
                output_path = Path(output_file)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(html_content, encoding='utf-8')
                logger.info(f"HTML report saved to {output_file}")
            
            return html_content
            
        except Exception as e:
            logger.error(f"Error generating HTML report: {e}")
            raise
