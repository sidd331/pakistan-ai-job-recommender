"""
=============================================================================
Email Notifications — sends daily digest alerts for high-relevance matches.
=============================================================================
Uses Flask-Mail (SMTP).  Gracefully skips if mail is not configured.
=============================================================================
"""

import logging
from datetime import datetime, timedelta, timezone

from flask_mail import Mail, Message
from models import db, User, Match, Job, Notification

logger = logging.getLogger(__name__)

mail = Mail()


# ---------------------------------------------------------------------------
# HTML EMAIL TEMPLATES
# ---------------------------------------------------------------------------
def send_welcome_email(user: User):
    """Send a welcome email upon successful registration."""
    from flask import current_app
    
    mail_user = current_app.config.get("MAIL_USERNAME", "")
    mail_pass = current_app.config.get("MAIL_PASSWORD", "")
    mail_sender = current_app.config.get("MAIL_DEFAULT_SENDER", "") or mail_user

    if not mail_user or not mail_pass:
        logger.warning(
            "⚠️  EMAIL NOT CONFIGURED — Welcome email skipped for %s. "
            "Set MAIL_USERNAME and MAIL_PASSWORD in your .env file.",
            user.email
        )
        return False

    if not mail_sender:
        logger.error(
            "⚠️  MAIL_DEFAULT_SENDER is empty and no fallback. "
            "Set MAIL_DEFAULT_SENDER or MAIL_USERNAME in .env."
        )
        return False

    logger.info(
        "📧 Attempting to send welcome email to %s via %s:%s (sender: %s)",
        user.email,
        current_app.config.get("MAIL_SERVER", "?"),
        current_app.config.get("MAIL_PORT", "?"),
        mail_sender,
    )

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin:0;padding:0;background:#0a0e27;font-family:'Segoe UI',Arial,sans-serif;">
        <div style="max-width:600px;margin:0 auto;padding:40px 20px;text-align:center;">
            <h1 style="color:#ffffff;font-size:28px;margin-bottom:16px;">Welcome to Pakistan Job AI! 🎉</h1>
            <p style="color:#a0a0b0;font-size:16px;line-height:1.6;margin-bottom:24px;">
                Hi <strong>{user.name}</strong>, your account has been successfully created.
            </p>
            <div style="background:#1a1f3a;padding:24px;border-radius:12px;text-align:left;margin-bottom:32px;display:inline-block;">
                <h3 style="color:#ffffff;margin-top:0;">Next Steps to Get Hired:</h3>
                <ul style="color:#a0a0b0;font-size:15px;line-height:1.8;margin-bottom:0;padding-left:20px;">
                    <li><strong>Upload your Resume/CV</strong> (PDF or DOCX) in the dashboard.</li>
                    <li>Let our AI analyze your skills and experience instantly.</li>
                    <li>Get matched with the most relevant jobs from 6 different portals.</li>
                    <li>Receive automated job alerts as soon as new jobs are posted!</li>
                </ul>
            </div>
            <p>
                <a href="{current_app.config.get('SITE_URL', 'http://localhost:5000')}/#dashboard" 
                   style="display:inline-block;background:linear-gradient(135deg,#667eea,#764ba2);color:#ffffff;text-decoration:none;padding:12px 32px;border-radius:8px;font-size:16px;font-weight:bold;">
                   Go to Dashboard →
                </a>
            </p>
        </div>
    </body>
    </html>
    """

    msg = Message(
        subject="Welcome to Pakistan Job AI! 🎉",
        recipients=[user.email],
        html=html_body,
        sender=mail_sender,
    )

    try:
        mail.send(msg)
        logger.info("✅ Welcome email sent successfully to %s", user.email)
        return True
    except Exception as e:
        error_str = str(e)
        if "Authentication" in error_str or "535" in error_str:
            logger.error(
                "❌ SMTP AUTHENTICATION FAILED for %s — Your MAIL_PASSWORD is likely "
                "wrong. Use a Gmail App Password (not your regular password). Error: %s",
                user.email, e
            )
        elif "Connection" in error_str or "timed out" in error_str:
            logger.error(
                "❌ SMTP CONNECTION FAILED — Cannot reach %s:%s. Check MAIL_SERVER "
                "and MAIL_PORT in .env. Error: %s",
                current_app.config.get("MAIL_SERVER"),
                current_app.config.get("MAIL_PORT"),
                e
            )
        else:
            logger.error("❌ Failed to send welcome email to %s: %s", user.email, e)
        return False

def _build_email_html(user_name: str, job_matches: list[dict]) -> str:
    """Build a professional HTML email body for the job digest."""
    job_cards = ""
    for m in job_matches:
        job = m["job"]
        score = m["score"]

        # Color based on score
        if score >= 80:
            color = "#00c853"
        elif score >= 60:
            color = "#ffd600"
        else:
            color = "#ff9800"

        link = job.get("link", "#")
        if not link or link == "nan":
            link = "#"

        job_cards += f"""
        <div style="background:#1a1f3a;border-radius:12px;padding:20px;margin-bottom:16px;border-left:4px solid {color};">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <h3 style="margin:0;color:#ffffff;font-size:16px;">{job.get('title', 'Untitled')}</h3>
                <span style="background:{color};color:#000;padding:4px 10px;border-radius:20px;font-weight:bold;font-size:13px;">
                    {score:.0f}% Match
                </span>
            </div>
            <p style="color:#a0a0b0;margin:8px 0 4px;">🏢 {job.get('company', 'N/A')}</p>
            <p style="color:#a0a0b0;margin:0 0 12px;">📍 {job.get('location', 'Pakistan')} &nbsp;|&nbsp; 🌐 {job.get('source', '')}</p>
            <a href="{link}" style="display:inline-block;background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;text-decoration:none;padding:8px 20px;border-radius:8px;font-size:14px;">
                Apply Now →
            </a>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin:0;padding:0;background:#0a0e27;font-family:'Segoe UI',Arial,sans-serif;">
        <div style="max-width:600px;margin:0 auto;padding:32px 20px;">
            <!-- Header -->
            <div style="text-align:center;padding:24px 0;">
                <h1 style="margin:0;color:#ffffff;font-size:24px;">
                    🎯 New Job Matches for You
                </h1>
                <p style="color:#a0a0b0;margin-top:8px;">
                    Hi {user_name}, we found jobs matching your profile!
                </p>
            </div>

            <!-- Job Cards -->
            {job_cards}

            <!-- Footer -->
            <div style="text-align:center;padding:24px 0;border-top:1px solid #2a2f4a;margin-top:24px;">
                <p style="color:#666;font-size:12px;">
                    You're receiving this because you have email notifications enabled.
                    <br>Log in to your account to manage notification preferences.
                </p>
                <p style="color:#667eea;font-size:13px;">
                    Pakistan Job AI — Intelligent Job Recommendation Platform
                </p>
            </div>
        </div>
    </body>
    </html>
    """


# ---------------------------------------------------------------------------
# SEND NOTIFICATION
# ---------------------------------------------------------------------------
def send_job_alerts(app):
    """
    Check all users with email notifications enabled.
    For each user, find new high-score matches (above threshold) that haven't
    been notified yet.  Send a digest email with all qualifying matches.

    This function is designed to be called after new jobs are synced.
    """
    with app.app_context():
        if not app.config.get("MAIL_USERNAME") or not app.config.get("MAIL_PASSWORD"):
            logger.info("Email not configured — skipping notifications.")
            return 0

        threshold = app.config.get("MATCH_THRESHOLD", 70)
        sent_count = 0

        # Only notify users who opted in
        users = User.query.filter_by(email_notifications=True).all()

        for user in users:
            try:
                # Find matches above threshold that haven't been notified
                existing_notif_job_ids = {
                    n.job_id for n in
                    Notification.query.filter_by(user_id=user.id, email_sent=True).all()
                }

                high_matches = (
                    Match.query
                    .filter_by(user_id=user.id)
                    .filter(Match.score >= threshold)
                    .order_by(Match.score.desc())
                    .all()
                )

                new_matches = [
                    m for m in high_matches
                    if m.job_id not in existing_notif_job_ids
                ]

                if not new_matches:
                    continue

                # Check daily frequency limit: skip if we sent an email today
                today_start = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                recent_notif = (
                    Notification.query
                    .filter_by(user_id=user.id, email_sent=True)
                    .filter(Notification.sent_at >= today_start)
                    .first()
                )
                if recent_notif:
                    continue  # already sent today

                # Build match data for the email
                match_data = []
                for m in new_matches[:10]:  # max 10 jobs per email
                    job = db.session.get(Job, m.job_id)
                    if job:
                        match_data.append({
                            "score": m.score,
                            "job": job.to_dict(),
                        })

                if not match_data:
                    continue

                # Send email
                html_body = _build_email_html(user.name or "there", match_data)
                msg = Message(
                    subject=f"🎯 {len(match_data)} New Job Matches — Pakistan Job AI",
                    recipients=[user.email],
                    html=html_body,
                )

                try:
                    mail.send(msg)
                    sent_count += 1
                    logger.info(f"Sent job alert to {user.email} ({len(match_data)} matches)")

                    # Record notifications
                    now = datetime.now(timezone.utc)
                    for m in new_matches[:10]:
                        notif = Notification(
                            user_id=user.id,
                            job_id=m.job_id,
                            score=m.score,
                            email_sent=True,
                            sent_at=now,
                        )
                        db.session.add(notif)
                    db.session.commit()

                except Exception as e:
                    logger.error(f"Failed to send email to {user.email}: {e}")
                    db.session.rollback()

            except Exception as e:
                logger.error(f"Notification processing failed for user {user.id}: {e}")

        logger.info(f"Notification round complete: {sent_count} emails sent.")
        return sent_count
