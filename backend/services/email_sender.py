import smtplib
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from config import settings

logger = logging.getLogger(__name__)

async def send_email_async(to_email, subject, body):
    """إرسال بريد إلكتروني بطريقة غير متزامنة"""
    
    # إعدادات الإرسال 
    smtp_server = settings.MAIL_SERVER or 'smtp.gmail.com'
    smtp_port = settings.MAIL_PORT or 587
    sender_email = settings.MAIL_DEFAULT_SENDER
    sender_password = settings.MAIL_PASSWORD or ""

    # إنشاء رسالة بريد إلكتروني
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = to_email
    message["Subject"] = subject
    
    # إضافة نص الرسالة
    message.attach(MIMEText(body, "plain"))

    try:
        # إرسال البريد باستخدام aiosmtplib
        await aiosmtplib.send(
            message,
            hostname=smtp_server,
            port=smtp_port,
            use_tls=True,
            username=sender_email,
            password=sender_password
        )
        logger.info(f"تم إرسال البريد الإلكتروني إلى {to_email} بنجاح")
        return True
    except Exception as e:
        logger.error(f"خطأ في إرسال البريد الإلكتروني: {str(e)}")
        return False

# دالة متزامنة للتوافق مع الكود القديم
def send_email(to_email, subject, body):
    """دالة متزامنة لإرسال البريد الإلكتروني للتوافق الخلفي"""
    
    # إعدادات الإرسال
    smtp_server = settings.MAIL_SERVER or 'smtp.gmail.com'
    smtp_port = settings.MAIL_PORT or 587
    sender_email = settings.MAIL_DEFAULT_SENDER
    sender_password = settings.MAIL_PASSWORD or ""

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = to_email

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, [to_email], msg.as_string())
        logger.info(f"تم إرسال البريد الإلكتروني إلى {to_email} بنجاح")
        return True
    except Exception as e:
        logger.error(f"خطأ في إرسال البريد الإلكتروني: {str(e)}")
        return False
