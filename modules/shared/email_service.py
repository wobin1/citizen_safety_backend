import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import os

# Configure logger
logger = logging.getLogger("email_service")
logging.basicConfig(level=logging.INFO)

class EmailService:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.from_email = os.getenv("FROM_EMAIL", self.smtp_username)
        
    def send_password_reset_email(self, to_email: str, reset_token: str, username: str) -> bool:
        """Send password reset email to user"""
        try:
            if not self.smtp_username or not self.smtp_password:
                logger.warning("SMTP credentials not configured. Email not sent.")
                return False
                
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = "Password Reset Request - Citizen Safety App"
            
            # Create reset URL (you'll need to replace with your frontend URL)
            frontend_url = os.getenv("FRONTEND_URL", "http://localhost:4200")
            reset_url = f"{frontend_url}/auth/reset-password?token={reset_token}"
            
            # Email body
            body = f"""
            Hello {username},
            
            You have requested to reset your password for the Citizen Safety App.
            
            Please click the link below to reset your password:
            {reset_url}
            
            This link will expire in 1 hour for security reasons.
            
            If you did not request this password reset, please ignore this email.
            
            Best regards,
            Citizen Safety App Team
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            text = msg.as_string()
            server.sendmail(self.from_email, to_email, text)
            server.quit()
            
            logger.info(f"Password reset email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send password reset email to {to_email}: {e}")
            return False

# Global email service instance
email_service = EmailService()

async def send_password_reset_email(to_email: str, reset_token: str, username: str) -> bool:
    """Async wrapper for sending password reset email"""
    return email_service.send_password_reset_email(to_email, reset_token, username)
