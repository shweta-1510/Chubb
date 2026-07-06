"""
Threshold evaluation utilities for health checks.
"""
from typing import Tuple
from app.config import config
from app.models.health_check_result import HealthStatus, ResourceMetric


class ThresholdEvaluator:
    """Evaluates resource metrics against configured thresholds."""
    
    def __init__(self):
        self.thresholds = config.thresholds
    
    def evaluate_cpu(self, usage: float) -> ResourceMetric:
        """
        Evaluate CPU usage against thresholds.
        
        Args:
            usage: CPU usage percentage (0-100)
            
        Returns:
            ResourceMetric with status evaluation
        """
        status = self._determine_status(
            usage,
            self.thresholds.cpu_warning,
            self.thresholds.cpu_critical
        )
        
        return ResourceMetric(
            usage=usage,
            status=status,
            threshold_warning=self.thresholds.cpu_warning,
            threshold_critical=self.thresholds.cpu_critical
        )
    
    def evaluate_memory(self, usage: float) -> ResourceMetric:
        """
        Evaluate memory usage against thresholds.
        
        Args:
            usage: Memory usage percentage (0-100)
            
        Returns:
            ResourceMetric with status evaluation
        """
        status = self._determine_status(
            usage,
            self.thresholds.memory_warning,
            self.thresholds.memory_critical
        )
        
        return ResourceMetric(
            usage=usage,
            status=status,
            threshold_warning=self.thresholds.memory_warning,
            threshold_critical=self.thresholds.memory_critical
        )
    
    def evaluate_disk(self, usage: float) -> ResourceMetric:
        """
        Evaluate disk usage against thresholds.
        
        Args:
            usage: Disk usage percentage (0-100)
            
        Returns:
            ResourceMetric with status evaluation
        """
        status = self._determine_status(
            usage,
            self.thresholds.disk_warning,
            self.thresholds.disk_critical
        )
        
        return ResourceMetric(
            usage=usage,
            status=status,
            threshold_warning=self.thresholds.disk_warning,
            threshold_critical=self.thresholds.disk_critical
        )
    
    @staticmethod
    def _determine_status(usage: float, warning_threshold: float, critical_threshold: float) -> HealthStatus:
        """
        Determine health status based on usage and thresholds.
        
        Args:
            usage: Resource usage percentage
            warning_threshold: Warning threshold percentage
            critical_threshold: Critical threshold percentage
            
        Returns:
            HealthStatus enum value
        """
        if usage >= critical_threshold:
            return HealthStatus.CRITICAL
        elif usage >= warning_threshold:
            return HealthStatus.WARNING
        else:
            return HealthStatus.HEALTHY
