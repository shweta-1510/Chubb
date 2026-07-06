"""
Email notification sender.
Sends health check reports via email using SMTP.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional
from pathlib import Path
import os

from app.utils.logger import get_logger

logger = get_logger(__name__)


class EmailSender:
    """Sends email notifications with health check reports."""
    
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = True
    ):
        """
        Initialize email sender.
        
        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port (default: 587)
            username: SMTP username (optional)
            password: SMTP password (optional)
            use_tls: Use TLS encryption (default: True)
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.use_tls = use_tls
    
    def send_report(
        self,
        to_addresses: List[str],
        subject: str,
        body_html: str,
        from_address: str,
        attachments: Optional[List[str]] = None,
        cc_addresses: Optional[List[str]] = None
    ) -> bool:
        """
        Send health check report via email.
        
        Args:
            to_addresses: List of recipient email addresses
            subject: Email subject
            body_html: HTML email body
            from_address: Sender email address
            attachments: Optional list of file paths to attach
            cc_addresses: Optional list of CC email addresses
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Create message
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = from_address
            message['To'] = ', '.join(to_addresses)
            
            if cc_addresses:
                message['Cc'] = ', '.join(cc_addresses)
            
            # Attach HTML body
            html_part = MIMEText(body_html, 'html')
            message.attach(html_part)
            
            # Attach files
            if attachments:
                for file_path in attachments:
                    self._attach_file(message, file_path)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                
                if self.username and self.password:
                    server.login(self.username, self.password)
                
                recipients = to_addresses + (cc_addresses or [])
                server.send_message(message)
            
            logger.info(f"Email sent successfully to {', '.join(to_addresses)}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    def _attach_file(self, message: MIMEMultipart, file_path: str) -> None:
        """
        Attach file to email message.
        
        Args:
            message: Email message object
            file_path: Path to file to attach
        """
        try:
            path = Path(file_path)
            
            if not path.exists():
                logger.warning(f"Attachment file not found: {file_path}")
                return
            
            with open(path, 'rb') as file:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(file.read())
            
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {path.name}'
            )
            
            message.attach(part)
            logger.debug(f"Attached file: {path.name}")
            
        except Exception as e:
            logger.error(f"Error attaching file {file_path}: {e}")
