"""
=============================================================================
Admin Panel — Flask Blueprint for system administration dashboard.
=============================================================================
Provides:
  - Dashboard statistics (users, jobs, matches, email status)
  - User management (view, toggle, delete — excludes admin's own account)
  - Job monitoring (per-source stats, active/total counts)
  - User profile viewing (resume metadata)
  - System actions (sync, rematch, notifications)
=============================================================================
"""

import logging
from functools import wraps
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user

from models import db, User, Job, Match, Profile, Notification

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not getattr(current_user, "is_admin", False):
            return jsonify({"error": "Admin privileges required."}), 403
        return f(*args, **kwargs)
    return decorated_function


# ---------------------------------------------------------------------------
# DASHBOARD STATISTICS
# ---------------------------------------------------------------------------
@admin_bp.route("/dashboard", methods=["GET"])
@admin_required
def dashboard_stats():
    """Return high-level platform statistics for the admin dashboard."""
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    users_with_profiles = db.session.query(Profile.user_id).distinct().count()

    total_jobs = Job.query.count()
    active_jobs = Job.query.filter_by(status="Active").count()

    total_matches = Match.query.count()
    total_notifications = Notification.query.filter_by(email_sent=True).count()

    # Per-source job breakdown
    source_stats = {}
    sources = db.session.query(Job.source, db.func.count(Job.id)).group_by(Job.source).all()
    for source, count in sources:
        if source and source.strip():
            source_stats[source.strip()] = count

    # Email configuration status
    mail_configured = bool(
        current_app.config.get("MAIL_USERNAME")
        and current_app.config.get("MAIL_PASSWORD")
    )

    return jsonify({
        "total_users": total_users,
        "active_users": active_users,
        "users_with_profiles": users_with_profiles,
        "total_jobs": total_jobs,
        "active_jobs": active_jobs,
        "total_matches": total_matches,
        "total_notifications_sent": total_notifications,
        "source_stats": source_stats,
        "mail_configured": mail_configured,
    })


# ---------------------------------------------------------------------------
# USERS MANAGEMENT  (admin's own account is excluded from the list)
# ---------------------------------------------------------------------------
@admin_bp.route("/users", methods=["GET"])
@admin_required
def get_users():
    """Return all users EXCEPT the currently logged-in admin."""
    users = (
        User.query
        .filter(User.id != current_user.id)      # ← exclude self
        .order_by(User.created_at.desc())
        .all()
    )
    user_list = []
    for u in users:
        d = u.to_dict()
        d["job_matches_count"] = Match.query.filter_by(user_id=u.id).count()
        d["has_resume"] = u.profile is not None
        d["resume_filename"] = u.profile.resume_filename if u.profile else None
        d["profile_updated"] = (
            u.profile.updated_at.isoformat() if u.profile and u.profile.updated_at else None
        )
        user_list.append(d)
    return jsonify({"users": user_list})


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@admin_required
def toggle_user(user_id):
    """Enable/disable a user account. Admin cannot toggle their own."""
    if user_id == current_user.id:
        return jsonify({"error": "Cannot modify your own account."}), 400

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404

    user.is_active = not user.is_active
    db.session.commit()
    status = "activated" if user.is_active else "disabled"
    logger.info(f"Admin {current_user.email} {status} user {user.email}")
    return jsonify({"message": f"User account {status}.", "is_active": user.is_active})


@admin_bp.route("/users/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id):
    """Permanently delete a user. Admin cannot delete their own account."""
    if user_id == current_user.id:
        return jsonify({"error": "Cannot delete your own account."}), 400

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404

    email = user.email
    db.session.delete(user)
    db.session.commit()
    logger.info(f"Admin {current_user.email} deleted user {email}")
    return jsonify({"message": f"User '{email}' deleted permanently."})


# ---------------------------------------------------------------------------
# USER PROFILE VIEWING  (admin can inspect any user's parsed resume data)
# ---------------------------------------------------------------------------
@admin_bp.route("/users/<int:user_id>/profile", methods=["GET"])
@admin_required
def view_user_profile(user_id):
    """View parsed resume data for a specific user."""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404

    if not user.profile:
        return jsonify({"error": "This user has not uploaded a resume."}), 404

    profile_data = user.profile.to_dict()
    profile_data["user_name"] = user.name
    profile_data["user_email"] = user.email
    return jsonify({"profile": profile_data})


# ---------------------------------------------------------------------------
# JOB MONITORING
# ---------------------------------------------------------------------------
@admin_bp.route("/jobs", methods=["GET"])
@admin_required
def get_job_stats():
    """Return per-source job breakdown for monitoring."""
    source_stats = []
    sources = (
        db.session.query(
            Job.source,
            db.func.count(Job.id).label("total"),
        )
        .group_by(Job.source)
        .all()
    )

    for source, total in sources:
        label = source.strip() if source and source.strip() else "Unknown"
        active = Job.query.filter_by(source=source, status="Active").count()
        source_stats.append({
            "source": label,
            "total": total,
            "active": active,
            "closed": total - active,
        })

    # Sort by total jobs descending
    source_stats.sort(key=lambda x: x["total"], reverse=True)

    return jsonify({
        "sources": source_stats,
        "total_jobs": Job.query.count(),
        "active_jobs": Job.query.filter_by(status="Active").count(),
    })


# ---------------------------------------------------------------------------
# SYSTEM ACTIONS
# ---------------------------------------------------------------------------
@admin_bp.route("/trigger/sync", methods=["POST"])
@admin_required
def trigger_sync():
    """Manually invoke the job sync from Excel script."""
    from job_sync import sync_jobs_from_excel
    try:
        new, total = sync_jobs_from_excel(current_app, trigger_rematch=True)
        logger.info(f"Admin {current_user.email} triggered sync: {new} new, {total} total")
        return jsonify({"message": f"Sync complete. {new} new jobs imported, {total} total."})
    except Exception as e:
        logger.error(f"Manual sync failed: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/trigger/matches", methods=["POST"])
@admin_required
def trigger_matches():
    """Manually re-run matching logic for all users."""
    try:
        from matcher import rematch_all_users
        import threading
        threading.Thread(target=rematch_all_users, daemon=True).start()
        logger.info(f"Admin {current_user.email} triggered global re-matching")
        return jsonify({"message": "Background re-matching process started for all users."})
    except Exception as e:
        logger.error(f"Manual match trigger failed: {e}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/trigger/notifications", methods=["POST"])
@admin_required
def trigger_notifications():
    """Manually trigger job email notifications."""
    from notifications import send_job_alerts
    try:
        sent_count = send_job_alerts(current_app)
        logger.info(f"Admin {current_user.email} triggered notifications: {sent_count} sent")
        return jsonify({"message": f"Notification sweep complete. Sent {sent_count} emails."})
    except Exception as e:
        logger.error(f"Manual notification trigger failed: {e}")
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# CUSTOM JOB SOURCES
# ---------------------------------------------------------------------------
from models import CustomSource

@admin_bp.route("/custom-sources", methods=["GET"])
@admin_required
def get_custom_sources():
    """Get all custom scraping sources configured by the admin."""
    sources = CustomSource.query.order_by(CustomSource.created_at.desc()).all()
    return jsonify({"sources": [s.to_dict() for s in sources]})


@admin_bp.route("/custom-sources", methods=["POST"])
@admin_required
def add_custom_source():
    """Add a new custom job website link for scraping."""
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    url = data.get("url", "").strip()
    
    if not name or not url:
        return jsonify({"error": "Name and URL are required."}), 400
    
    source = CustomSource(name=name, url=url)
    db.session.add(source)
    db.session.commit()
    logger.info(f"Admin {current_user.email} added custom source {name} ({url})")
    return jsonify({"message": "Custom source added.", "source": source.to_dict()})


@admin_bp.route("/custom-sources/<int:id>", methods=["DELETE"])
@admin_required
def delete_custom_source(id):
    """Delete a custom job source."""
    source = db.session.get(CustomSource, id)
    if source:
        db.session.delete(source)
        db.session.commit()
        logger.info(f"Admin {current_user.email} deleted custom source {source.name}")
    return jsonify({"message": "Custom source deleted."})
