"""
=============================================================================
Configuration — reads .env and exposes settings used across the app.
=============================================================================
"""

import os
from dotenv import load_dotenv

load_dotenv()  # reads .env in project root

_BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    BASE_DIR = _BASE_DIR

    # ---- Flask core ----
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG = os.getenv("FLASK_DEBUG", "true").lower() in ("true", "1", "yes")

    # ---- Database (SQLite) ----
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(_BASE_DIR, "instance", "jobs.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ---- File uploads ----
    UPLOAD_FOLDER = os.path.join(_BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB

    # ---- Google OAuth (optional) ----
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

    # ---- Flask-Mail / SMTP (optional) ----
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() in ("true", "1")
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.getenv(
        "MAIL_DEFAULT_SENDER",
        os.getenv("MAIL_USERNAME", "")  # fallback: use MAIL_USERNAME if sender not set
    )

    # ---- Matching ----
    MATCH_THRESHOLD = int(os.getenv("MATCH_THRESHOLD", 70))

    # ---- Excel source ----
    EXCEL_FILE = os.path.join(_BASE_DIR, "Pakistan_Jobs_Report.xlsx")

    # ---- Convenience flags ----
    @property
    def google_oauth_enabled(self):
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET)

    @property
    def mail_enabled(self):
        return bool(self.MAIL_USERNAME and self.MAIL_PASSWORD)
