"""Gmail SMTP mailer for sending digest emails."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging

from idea_radar.config import Config


logger = logging.getLogger(__name__)


class GmailMailer:
    """Send emails via Gmail SMTP."""
    
    def __init__(self, config: Config):
        """Initialize Gmail mailer with configuration.
        
        Args:
            config: Application configuration containing email settings.
        """
        self.config = config.email
        self.smtp_host = self.config.smtp_host
        self.smtp_port = self.config.smtp_port
        self.sender = self.config.sender
        self.password = self.config.password
        self.recipient = self.config.recipient
    
    def send(self, subject: str, html_body: str) -> bool:
        """Send email via Gmail SMTP.
        
        Args:
            subject: Email subject line.
            html_body: HTML content for email body.
            
        Returns:
            True on success, False on failure.
        """
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.sender
            msg["To"] = self.recipient
            msg["Reply-To"] = self.sender
            
            # Attach HTML part
            html_part = MIMEText(html_body, "html", "utf-8")
            msg.attach(html_part)
            
            # Send via SMTP with STARTTLS
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender, self.password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {self.recipient}")
            return True
            
        except smtplib.SMTPAuthenticationError:
            logger.error(f"Gmail authentication failed. Check sender email and password/app password.")
            return False
            
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error while sending email: {e}")
            return False
            
        except Exception as e:
            logger.error(f"Unexpected error while sending email: {e}")
            return False