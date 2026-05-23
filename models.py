"""
=============================================================================
Database Models — SQLAlchemy ORM models for the job recommendation platform.
=============================================================================
Tables: Users, Profiles, Jobs, Matches, Notifications
=============================================================================
"""

import json
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


# ---------------------------------------------------------------------------
# USERS
# ---------------------------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)  # null for OAuth-only
    name = db.Column(db.String(255), nullable=False, default="")
    auth_provider = db.Column(db.String(50), default="local")  # local | google
    google_id = db.Column(db.String(255), unique=True, nullable=True)
    email_notifications = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    profile = db.relationship("Profile", backref="user", uselist=False,
                              cascade="all, delete-orphan")
    matches = db.relationship("Match", backref="user", lazy="dynamic",
                              cascade="all, delete-orphan")
    notifications = db.relationship("Notification", backref="user", lazy="dynamic",
                                    cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "auth_provider": self.auth_provider,
            "email_notifications": self.email_notifications,
            "is_admin": self.is_admin,
            "is_active": self.is_active,
            "has_profile": self.profile is not None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# PROFILES  (parsed resume data, 1-per-user)
# ---------------------------------------------------------------------------
class Profile(db.Model):
    __tablename__ = "profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    resume_filename = db.Column(db.String(255), default="")
    raw_text = db.Column(db.Text, default="")
    skills_json = db.Column(db.Text, default="[]")
    education_json = db.Column(db.Text, default="[]")
    experience_json = db.Column(db.Text, default="[]")
    locations_json = db.Column(db.Text, default="[]")
    job_titles_json = db.Column(db.Text, default="[]")
    experience_years = db.Column(db.Integer, default=0)
    summary = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    # ---------- convenience helpers ----------
    @property
    def skills(self):
        try:
            return json.loads(self.skills_json)
        except (json.JSONDecodeError, TypeError):
            return []

    @skills.setter
    def skills(self, value):
        self.skills_json = json.dumps(value)

    @property
    def education(self):
        try:
            return json.loads(self.education_json)
        except (json.JSONDecodeError, TypeError):
            return []

    @education.setter
    def education(self, value):
        self.education_json = json.dumps(value)

    @property
    def experience(self):
        try:
            return json.loads(self.experience_json)
        except (json.JSONDecodeError, TypeError):
            return []

    @experience.setter
    def experience(self, value):
        self.experience_json = json.dumps(value)

    @property
    def locations(self):
        try:
            return json.loads(self.locations_json)
        except (json.JSONDecodeError, TypeError):
            return []

    @locations.setter
    def locations(self, value):
        self.locations_json = json.dumps(value)

    @property
    def job_titles(self):
        try:
            return json.loads(self.job_titles_json)
        except (json.JSONDecodeError, TypeError):
            return []

    @job_titles.setter
    def job_titles(self, value):
        self.job_titles_json = json.dumps(value)

    def to_dict(self):
        return {
            "resume_filename": self.resume_filename,
            "skills": self.skills,
            "education": self.education,
            "experience": self.experience,
            "locations": self.locations,
            "job_titles": self.job_titles,
            "experience_years": self.experience_years,
            "summary": self.summary,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ---------------------------------------------------------------------------
# JOBS  (imported from Excel)
# ---------------------------------------------------------------------------
class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    company = db.Column(db.String(500), default="")
    location = db.Column(db.String(255), default="")
    source = db.Column(db.String(100), default="")
    link = db.Column(db.String(1000), default="", index=True)
    date_scraped = db.Column(db.String(50), default="")
    posted_date = db.Column(db.String(100), default="")
    deadline = db.Column(db.String(100), default="")
    status = db.Column(db.String(50), default="Active")
    requirements = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    matches = db.relationship("Match", backref="job", lazy="dynamic",
                              cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "source": self.source,
            "link": self.link,
            "date_scraped": self.date_scraped,
            "posted_date": self.posted_date,
            "deadline": self.deadline,
            "status": self.status,
        }


# ---------------------------------------------------------------------------
# MATCHES  (user <-> job with score)
# ---------------------------------------------------------------------------
class Match(db.Model):
    __tablename__ = "matches"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False)
    score = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("user_id", "job_id", name="uq_user_job"),
    )

    def to_dict(self):
        job = self.job
        return {
            "id": self.id,
            "score": round(self.score, 1),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "job": job.to_dict() if job else {},
        }


# ---------------------------------------------------------------------------
# CUSTOM SOURCES  (Admin configured scraping targets)
# ---------------------------------------------------------------------------
class CustomSource(db.Model):
    __tablename__ = "custom_sources"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(1000), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# NOTIFICATIONS  (email alerts sent)
# ---------------------------------------------------------------------------
class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False)
    score = db.Column(db.Float, default=0.0)
    email_sent = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
