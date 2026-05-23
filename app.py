"""
=============================================================================
Pakistan Job AI — Flask Application (Main Entry Point)
=============================================================================
Serves the web UI and all API endpoints.

Usage:
    python app.py
    → Opens at http://localhost:5000
=============================================================================
"""

import os
import sys
import logging

# Force UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from flask import Flask, request, jsonify, send_from_directory
from flask_login import LoginManager, login_required, current_user
from flask_cors import CORS

from config import Config
from models import db, User, Job, Match, Profile
from auth import auth_bp
from admin import admin_bp
from notifications import mail

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# APP FACTORY
# ---------------------------------------------------------------------------
def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(Config)

    # Ensure folders exist
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(os.path.join(Config.BASE_DIR, "instance"), exist_ok=True)

    # ---- Extensions ----
    db.init_app(app)
    CORS(app, supports_credentials=True)
    mail.init_app(app)

    # ---- Flask-Login ----
    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify({"error": "Authentication required."}), 401

    # ---- Register blueprints ----
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)

    # ---- Create database tables ----
    with app.app_context():
        db.create_all()

        # Seed default admin account if none exists
        _seed_admin(app)

        # 1. Scrape latest jobs and update Excel
        logger.info("Starting initial job scraping. This may take a few minutes...")
        try:
            from scraper_agent import run_scraping_cycle
            run_scraping_cycle()
        except Exception as e:
            logger.error(f"Initial scraping failed: {e}")

        # 2. Sync jobs from Excel to the Database
        from job_sync import sync_jobs_from_excel
        try:
            new, total = sync_jobs_from_excel(app, trigger_rematch=False)
            logger.info(f"Initial job sync: {new} new, {total} total jobs.")
        except Exception as e:
            logger.error(f"Initial sync failed: {e}")

    # ---- Start background sync thread ----
    from job_sync import start_sync_thread
    start_sync_thread(app, interval_seconds=300)  # every 5 minutes

    # ---- Register API routes ----
    _register_routes(app)

    # ---- Email config health-check ----
    if app.config.get("MAIL_USERNAME") and app.config.get("MAIL_PASSWORD"):
        logger.info(
            "📧 Email configured: server=%s, port=%s, sender=%s",
            app.config.get("MAIL_SERVER"),
            app.config.get("MAIL_PORT"),
            app.config.get("MAIL_DEFAULT_SENDER") or app.config.get("MAIL_USERNAME"),
        )
    else:
        logger.warning(
            "⚠️  Email NOT configured — registration emails and job alerts will be SKIPPED. "
            "Set MAIL_USERNAME and MAIL_PASSWORD in your .env file."
        )

    # ---- Google OAuth health-check ----
    if app.config.get("GOOGLE_CLIENT_ID") and app.config.get("GOOGLE_CLIENT_SECRET"):
        logger.info("🔑 Google OAuth configured and ready.")
    else:
        logger.warning(
            "⚠️  Google OAuth NOT configured — 'Continue with Google' button will be hidden. "
            "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your .env file."
        )

    return app


# ---------------------------------------------------------------------------
# ADMIN SEEDING
# ---------------------------------------------------------------------------
def _seed_admin(app):
    """Create a default admin account if no admin exists in the database."""
    from werkzeug.security import generate_password_hash

    admin_exists = User.query.filter_by(is_admin=True).first()
    if admin_exists:
        return  # already have an admin

    default_email = "admin@jobai.pk"
    default_password = "admin123"
    default_name = "Admin"

    # Check if this email is already taken (but not admin)
    existing = User.query.filter_by(email=default_email).first()
    if existing:
        existing.is_admin = True
        db.session.commit()
        logger.info(f"🔑 Promoted existing user '{default_email}' to admin.")
        return

    admin = User(
        email=default_email,
        password_hash=generate_password_hash(default_password, method="pbkdf2:sha256"),
        name=default_name,
        auth_provider="local",
        is_admin=True,
        is_active=True,
    )
    db.session.add(admin)
    db.session.commit()
    logger.info("=" * 60)
    logger.info("🔑 DEFAULT ADMIN ACCOUNT CREATED:")
    logger.info("   Email:    %s", default_email)
    logger.info("   Password: %s", default_password)
    logger.info("   ⚠️  CHANGE THIS PASSWORD after first login!")
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# API ROUTES
# ---------------------------------------------------------------------------
def _register_routes(app: Flask):

    # ---------- FRONTEND ----------
    @app.route("/")
    def index():
        return send_from_directory("templates", "index.html")

    # ---------- RESUME UPLOAD ----------
    @app.route("/api/upload-resume", methods=["POST"])
    @login_required
    def upload_resume():
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded."}), 400

        file = request.files["file"]
        if not file.filename:
            return jsonify({"error": "Empty filename."}), 400

        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in ("pdf", "docx"):
            return jsonify({"error": "Only PDF and DOCX files are supported."}), 400

        # Save file
        safe_name = f"resume_{current_user.id}.{ext}"
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)
        file.save(save_path)

        # Parse resume
        from resume_parser import parse_resume
        try:
            profile_data = parse_resume(save_path)
        except Exception as e:
            logger.error(f"Resume parsing failed: {e}")
            return jsonify({"error": f"Failed to parse resume: {str(e)}"}), 500

        # Persist profile
        profile = current_user.profile
        if not profile:
            profile = Profile(user_id=current_user.id)
            db.session.add(profile)

        profile.resume_filename = file.filename
        profile.raw_text = profile_data.get("raw_text", "")
        profile.skills = profile_data.get("skills", [])
        profile.education = profile_data.get("education", [])
        profile.experience = profile_data.get("experience", [])
        profile.locations = profile_data.get("locations", [])
        profile.job_titles = profile_data.get("job_titles", [])
        profile.experience_years = profile_data.get("experience_years", 0)
        profile.summary = profile_data.get("summary", "")

        db.session.commit()

        # Trigger matching
        from matcher import compute_matches_for_user
        try:
            matches = compute_matches_for_user(current_user.id)
        except Exception as e:
            logger.error(f"Matching failed after upload: {e}")
            matches = []

        return jsonify({
            "message": "Resume uploaded and parsed successfully.",
            "profile": profile.to_dict(),
            "matches_count": len(matches),
        })

    # ---------- GET PROFILE ----------
    @app.route("/api/profile", methods=["GET"])
    @login_required
    def get_profile():
        if current_user.profile:
            return jsonify({"profile": current_user.profile.to_dict()})
        return jsonify({"profile": None})

    # ---------- DELETE PROFILE ----------
    @app.route("/api/profile", methods=["DELETE"])
    @login_required
    def delete_profile():
        if current_user.profile:
            db.session.delete(current_user.profile)
            Match.query.filter_by(user_id=current_user.id).delete()
            db.session.commit()
            return jsonify({"message": "Profile and matches deleted."})
        return jsonify({"message": "No profile to delete."})

    # ---------- GET ALL JOBS ----------
    @app.route("/api/jobs", methods=["GET"])
    def get_jobs():
        query = Job.query.filter_by(status="Active")

        # Filters
        source = request.args.get("source", "").strip()
        if source:
            query = query.filter(Job.source.ilike(f"%{source}%"))

        location = request.args.get("location", "").strip()
        if location:
            query = query.filter(Job.location.ilike(f"%{location}%"))

        search = request.args.get("search", "").strip()
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                db.or_(
                    Job.title.ilike(pattern),
                    Job.company.ilike(pattern),
                    Job.location.ilike(pattern),
                )
            )

        sort_by = request.args.get("sort", "date").strip().lower()
        if sort_by == "relevance" and current_user.is_authenticated:
            # We can't easily sort by pure Python relevance here, but if the user requested relevance 
            # and they have matches, they should really be looking at the matches endpoint.
            # We will fallback to date here since /jobs is for browsing all jobs.
            jobs = query.order_by(Job.date_scraped.desc()).all()
        elif sort_by == "deadline":
            # order by deadline ascending, but put empty deadlines at end
            jobs = query.order_by(
                db.case(
                    (Job.deadline == '', 1),
                    (Job.deadline == 'nan', 1),
                    else_=0
                ),
                Job.deadline.asc()
            ).all()
        else: # date
            jobs = query.order_by(Job.date_scraped.desc()).all()
            
        return jsonify({
            "jobs": [j.to_dict() for j in jobs],
            "total": len(jobs),
        })

    # ---------- GET MATCHES ----------
    @app.route("/api/matches", methods=["GET"])
    @login_required
    def get_matches():
        matches = (
            Match.query
            .filter_by(user_id=current_user.id)
            .order_by(Match.score.desc())
            .all()
        )
        return jsonify({
            "matches": [m.to_dict() for m in matches],
            "total": len(matches),
        })

    # ---------- TRIGGER RE-MATCH ----------
    @app.route("/api/match", methods=["POST"])
    @login_required
    def trigger_match():
        if not current_user.profile:
            return jsonify({"error": "Upload a resume first."}), 400

        from matcher import compute_matches_for_user
        matches = compute_matches_for_user(current_user.id)
        return jsonify({
            "message": f"Matching complete. Found {len(matches)} jobs.",
            "matches_count": len(matches),
        })

    # ---------- STATISTICS ----------
    @app.route("/api/stats", methods=["GET"])
    def get_stats():
        total_jobs = Job.query.filter_by(status="Active").count()
        total_users = User.query.count()

        # Source breakdown
        sources = db.session.query(Job.source, db.func.count(Job.id))\
            .filter_by(status="Active").group_by(Job.source).all()
        source_counts = {s: c for s, c in sources}

        # Latest scrape date
        latest = db.session.query(db.func.max(Job.date_scraped)).scalar()

        return jsonify({
            "total_jobs": total_jobs,
            "total_users": total_users,
            "sources": source_counts,
            "last_updated": latest or "N/A",
        })

    # ---------- USER SETTINGS ----------
    @app.route("/api/settings", methods=["PUT"])
    @login_required
    def update_settings():
        data = request.get_json(silent=True) or {}
        if "email_notifications" in data:
            current_user.email_notifications = bool(data["email_notifications"])
        if "name" in data:
            name = str(data["name"]).strip()
            if name:
                current_user.name = name
        db.session.commit()
        return jsonify({"message": "Settings updated.", "user": current_user.to_dict()})

    # ---------- AVAILABLE FILTER OPTIONS ----------
    @app.route("/api/filters", methods=["GET"])
    def get_filters():
        sources = [r[0] for r in
                   db.session.query(Job.source).distinct().all() if r[0]]
        locations_raw = [r[0] for r in
                         db.session.query(Job.location).distinct().all() if r[0]]
        # Simplify common locations
        locations = sorted(set(locations_raw))
        return jsonify({"sources": sorted(sources), "locations": locations})

    # ---------- FRONTEND FEATURE CONFIG ----------
    @app.route("/api/config", methods=["GET"])
    def get_config():
        """Return feature availability flags so the frontend can show/hide UI elements."""
        return jsonify({
            "google_oauth_enabled": bool(
                app.config.get("GOOGLE_CLIENT_ID") and app.config.get("GOOGLE_CLIENT_SECRET")
            ),
            "email_enabled": bool(
                app.config.get("MAIL_USERNAME") and app.config.get("MAIL_PASSWORD")
            ),
        })


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  [%(levelname)-8s]  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    app = create_app()
    print("\n" + "=" * 60)
    print("  🎯  Pakistan Job AI — Intelligent Recommendation Platform")
    print("  📡  http://localhost:5000")
    print("=" * 60 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=Config.DEBUG)
