import secrets
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app, url_for

from app import db
from app.models import EmailConfirmationSetting, SmtpSetting


def get_confirmation_settings():
    try:
        setting = EmailConfirmationSetting.query.first()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return EmailConfirmationSetting(enabled=False)
    if not setting:
        setting = EmailConfirmationSetting(enabled=False)
        db.session.add(setting)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
    return setting


def is_email_confirmation_required():
    try:
        setting = get_confirmation_settings()
        return setting.enabled
    except Exception:
        return False


def generate_confirm_token(user):
    token = secrets.token_urlsafe(48)
    user.email_confirm_token = token
    user.email_confirm_sent_at = datetime.utcnow()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return None
    return token


def send_confirmation_email(user):
    smtp = SmtpSetting.query.first()
    if not smtp or not smtp.enabled:
        current_app.logger.warning("SMTP not configured, cannot send confirmation email")
        return False

    token = generate_confirm_token(user)
    if not token:
        return False

    setting = get_confirmation_settings()
    subject = setting.email_subject or 'Conferma il tuo indirizzo email - SONACIP'

    confirm_url = url_for('auth.confirm_email', token=token, _external=True)

    try:
        from flask import render_template as rt
        html_body = rt('emails/confirm_email.html', user=user, confirm_url=confirm_url, expiry_hours=setting.token_expiry_hours or 48)
    except Exception:
        html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #f0f2f5;">
        <div style="background: linear-gradient(135deg, #1877f2 0%, #42a5f5 100%); color: #fff; padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
            <h1 style="margin: 0; font-size: 28px;">🏆 SONACIP</h1>
            <p style="margin: 8px 0 0; opacity: 0.9; font-size: 14px;">Piattaforma Gestione Sportiva</p>
        </div>
        <div style="padding: 30px; background: #ffffff; border: 1px solid #e4e6eb;">
            <h2 style="color: #1c1e21; margin-top: 0;">Ciao {user.first_name or user.username}! 👋</h2>
            <p style="color: #606770; font-size: 16px; line-height: 1.6;">
                Conferma il tuo indirizzo email cliccando il pulsante qui sotto.
            </p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{confirm_url}" 
                   style="display: inline-block; background: #1877f2; color: #ffffff; padding: 14px 40px; border-radius: 8px; text-decoration: none; font-size: 16px; font-weight: 600;">
                    ✅ Conferma Email
                </a>
            </div>
            <p style="color: #8a8d91; font-size: 12px;">
                Questo link scade tra {setting.token_expiry_hours or 48} ore.
            </p>
        </div>
    </div>
    """

    text_body = f"""Ciao {user.first_name or user.username},

Grazie per esserti registrato su SONACIP.
Per confermare il tuo indirizzo email, visita il seguente link:

{confirm_url}

Il link scade tra {setting.token_expiry_hours or 48} ore.

Se non hai creato un account su SONACIP, ignora questa email.

SONACIP - Piattaforma Gestione Sportiva"""

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = smtp.default_sender or 'noreply@sonacip.it'
        msg['To'] = user.email
        msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        server = smtplib.SMTP(smtp.host, smtp.port)
        if smtp.use_tls:
            server.starttls()
        if smtp.username and smtp.password:
            server.login(smtp.username, smtp.password)
        server.sendmail(msg['From'], [user.email], msg.as_string())
        server.quit()
        return True
    except Exception:
        current_app.logger.exception("Failed to send confirmation email to %s", user.email)
        return False


def can_resend(user):
    setting = get_confirmation_settings()
    if not setting.enabled:
        return False, "Conferma email non richiesta"

    if user.email_confirmed:
        return False, "Email già confermata"

    if user.email_confirm_sent_at:
        elapsed = (datetime.utcnow() - user.email_confirm_sent_at).total_seconds()
        if elapsed < 60:
            return False, "Attendi almeno 60 secondi prima di richiedere un nuovo invio"

    return True, ""


def verify_token(token):
    if not token:
        return None, "Token mancante"

    from app.models import User
    user = User.query.filter_by(email_confirm_token=token).first()
    if not user:
        return None, "Token non valido o già utilizzato"

    if user.email_confirmed:
        return user, "Email già confermata"

    setting = get_confirmation_settings()
    expiry_hours = setting.token_expiry_hours or 48

    if user.email_confirm_sent_at:
        elapsed = (datetime.utcnow() - user.email_confirm_sent_at).total_seconds()
        if elapsed > expiry_hours * 3600:
            return None, "Il link di conferma è scaduto. Richiedi un nuovo invio."

    user.email_confirmed = True
    user.email_confirm_token = None
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return None, "Errore durante la conferma"

    return user, "Email confermata con successo"
