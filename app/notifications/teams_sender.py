"""
Microsoft Teams notification sender.
Sends health check alerts to Teams channels via webhooks.
"""
import requests
from typing import List, Dict, Any, Optional

from app.models.health_check_result import HealthCheckResult, HealthStatus
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TeamsSender:
    """Sends notifications to Microsoft Teams channels."""
    
    def __init__(self, webhook_url: str):
        """
        Initialize Teams sender.
        
        Args:
            webhook_url: Microsoft Teams incoming webhook URL
        """
        self.webhook_url = webhook_url
    
    def send_health_check_summary(
        self,
        results: List[HealthCheckResult],
        title: str = "Health Check Summary"
    ) -> bool:
        """
        Send health check summary to Teams channel.
        
        Args:
            results: List of health check results
            title: Card title
            
        Returns:
            True if notification sent successfully, False otherwise
        """
        try:
            # Build adaptive card
            card = self._build_summary_card(results, title)
            
            # Send to Teams
            response = requests.post(
                self.webhook_url,
                json=card,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("Teams notification sent successfully")
                return True
            else:
                logger.error(f"Failed to send Teams notification: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending Teams notification: {e}")
            return False
    
    def _build_summary_card(self, results: List[HealthCheckResult], title: str) -> Dict[str, Any]:
        """
        Build Microsoft Teams adaptive card.
        
        Args:
            results: List of health check results
            title: Card title
            
        Returns:
            Adaptive card dictionary
        """
        # Calculate summary statistics
        total = len(results)
        healthy = sum(1 for r in results if r.overall_status == HealthStatus.HEALTHY)
        warning = sum(1 for r in results if r.overall_status == HealthStatus.WARNING)
        critical = sum(1 for r in results if r.overall_status == HealthStatus.CRITICAL)
        failed = sum(1 for r in results if r.overall_status == HealthStatus.FAILED)
        
        # Determine overall color
        if critical > 0 or failed > 0:
            theme_color = "FF0000"  # Red
        elif warning > 0:
            theme_color = "FFA500"  # Orange
        else:
            theme_color = "00FF00"  # Green
        
        # Build facts
        facts = [
            {"name": "Total Servers", "value": str(total)},
            {"name": "✅ Healthy", "value": str(healthy)},
            {"name": "⚠️ Warning", "value": str(warning)},
            {"name": "🔴 Critical", "value": str(critical)},
            {"name": "❌ Failed", "value": str(failed)},
        ]
        
        # Build server status list
        server_status_text = []
        for result in results:
            status_emoji = self._get_status_emoji(result.overall_status)
            server_status_text.append(
                f"{status_emoji} **{result.server_name}** ({result.ip_address}) - {result.overall_status.value}"
            )
        
        # Create card
        card = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": title,
            "themeColor": theme_color,
            "title": title,
            "sections": [
                {
                    "activityTitle": "Environment Health Check Report",
                    "facts": facts,
                    "text": "\n\n".join(server_status_text[:10])  # Limit to first 10 servers
                }
            ],
            "potentialAction": [
                {
                    "@type": "OpenUri",
                    "name": "View Full Report",
                    "targets": [
                        {
                            "os": "default",
                            "uri": "http://your-app-url/reports"
                        }
                    ]
                }
            ]
        }
        
        if len(results) > 10:
            card["sections"][0]["text"] += f"\n\n... and {len(results) - 10} more servers"
        
        return card
    
    @staticmethod
    def _get_status_emoji(status: HealthStatus) -> str:
        """Get emoji for health status."""
        emoji_map = {
            HealthStatus.HEALTHY: "✅",
            HealthStatus.WARNING: "⚠️",
            HealthStatus.CRITICAL: "🔴",
            HealthStatus.FAILED: "❌",
            HealthStatus.UNKNOWN: "❓",
        }
        return emoji_map.get(status, "❓")
