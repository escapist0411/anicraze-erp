import logging
import asyncio
import smtplib
from email.message import EmailMessage

from app.config.settings import get_settings
from app.models.auth import User

logger = logging.getLogger(__name__)


class EmailService:
    """Delivers account communications through the configured application channel."""

    async def send_password_reset(self, user: User, reset_token: str) -> None:
        settings = get_settings()
        if settings.environment == "development":
            logger.info("Password reset requested for user_id=%s; use /reset-password?token=%s", user.id, reset_token)
        else:
            logger.info("Password reset email dispatch requested for user_id=%s", user.id)

    async def send_report(self,recipient:str,subject:str,body:str,filename:str,pdf:bytes)->dict:
        settings=get_settings()
        if not settings.mail_enabled:return {"status":"DISABLED","provider":settings.mail_provider,"failure_reason":"MAIL_ENABLED is false"}
        if not settings.smtp_host:return {"status":"FAILED","provider":"smtp","failure_reason":"SMTP_HOST is not configured"}
        message=EmailMessage();message["From"]=settings.mail_from;message["To"]=recipient;message["Subject"]=subject;message.set_content(body);message.add_attachment(pdf,maintype="application",subtype="pdf",filename=filename)
        def send():
            with smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=20) as smtp:
                if settings.smtp_use_tls:smtp.starttls()
                if settings.smtp_username:smtp.login(settings.smtp_username,settings.smtp_password or "")
                smtp.send_message(message)
        try:await asyncio.to_thread(send);return {"status":"SENT","provider":"smtp","failure_reason":None}
        except Exception as exc:
            logger.exception("Weekly report email failed");return {"status":"FAILED","provider":"smtp","failure_reason":str(exc)[:500]}
