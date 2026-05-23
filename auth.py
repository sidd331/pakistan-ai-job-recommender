"""
=============================================================================
Authentication — Flask Blueprint for registration, login, logout, OAuth.
=============================================================================
"""

import logging
from functools import wraps

from flask import Blueprint, request, jsonify, redirect, url_for, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def _json_error(msg, status=400):
    return jsonify({"error": msg}), status


def _validate_email(email: str) -> bool:
    import re
    return bool(re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email))


# ---------------------------------------------------------------------------
# REGISTER
# ---------------------------------------------------------------------------
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    name = (data.get("name") or "").strip()

    if not email or not _validate_email(email):
        return _json_error("Valid email is required.")
    if not password or len(password) < 6:
        return _json_error("Password must be at least 6 characters.")
    if not name:
        return _json_error("Name is required.")

    existing = User.query.filter_by(email=email).first()
    if existing:
        return _json_error("An account with this email already exists.")

    user = User(
        email=email,
        password_hash=generate_password_hash(password, method="pbkdf2:sha256"),
        name=name,
        auth_provider="local",
        is_admin=False,  # Admin accounts are NEVER created via public registration
    )
    db.session.add(user)
    db.session.commit()
    login_user(user, remember=True)
    logger.info(f"New user registered: {email}")

    from notifications import send_welcome_email
    send_welcome_email(user)

    return jsonify({"message": "Account created successfully.", "user": user.to_dict()}), 201


# ---------------------------------------------------------------------------
# LOGIN
# ---------------------------------------------------------------------------
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return _json_error("Email and password are required.")

    user = User.query.filter_by(email=email).first()
    if not user or not user.password_hash:
        return _json_error("Invalid email or password.", 401)
    if not check_password_hash(user.password_hash, password):
        return _json_error("Invalid email or password.", 401)
    if not user.is_active:
        return _json_error("Your account has been disabled by an administrator.", 403)

    login_user(user, remember=True)
    logger.info(f"User logged in: {email}")

    return jsonify({"message": "Logged in.", "user": user.to_dict()})


# ---------------------------------------------------------------------------
# LOGOUT
# ---------------------------------------------------------------------------
@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    email = current_user.email
    logout_user()
    logger.info(f"User logged out: {email}")
    return jsonify({"message": "Logged out."})


# ---------------------------------------------------------------------------
# CURRENT USER
# ---------------------------------------------------------------------------
@auth_bp.route("/me", methods=["GET"])
def me():
    if current_user.is_authenticated:
        return jsonify({"user": current_user.to_dict()})
    return jsonify({"user": None}), 200


# ---------------------------------------------------------------------------
# GOOGLE OAUTH 2.0  (optional — only active if credentials configured)
# ---------------------------------------------------------------------------
_oauth = None  # lazy-initialized


def _get_oauth(app):
    """Lazily initialise Authlib OAuth client."""
    global _oauth
    if _oauth is not None:
        return _oauth
    try:
        from authlib.integrations.flask_client import OAuth
        _oauth = OAuth(app)
        _oauth.register(
            name="google",
            client_id=app.config["GOOGLE_CLIENT_ID"],
            client_secret=app.config["GOOGLE_CLIENT_SECRET"],
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )
        return _oauth
    except Exception as e:
        logger.warning(f"Google OAuth setup failed: {e}")
        return None


@auth_bp.route("/google", methods=["GET"])
def google_login():
    cfg = current_app.config
    if not cfg.get("GOOGLE_CLIENT_ID") or not cfg.get("GOOGLE_CLIENT_SECRET"):
        return _json_error("Google OAuth is not configured on this server.", 501)
    oauth = _get_oauth(current_app)
    if not oauth:
        return _json_error("OAuth initialization failed.", 500)
    redirect_uri = url_for("auth.google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route("/google/callback", methods=["GET"])
def google_callback():
    oauth = _get_oauth(current_app)
    if not oauth:
        return redirect("/#login")
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get("userinfo") or oauth.google.userinfo()
        google_id = user_info.get("sub", "")
        email = user_info.get("email", "").lower()
        name = user_info.get("name", email.split("@")[0])

        if not email:
            return redirect("/#login")

        # Find or create user
        user = User.query.filter_by(google_id=google_id).first()
        if not user:
            user = User.query.filter_by(email=email).first()
        if not user:
            user = User(
                email=email,
                name=name,
                auth_provider="google",
                google_id=google_id,
            )
            db.session.add(user)
        else:
            if not user.is_active:
                return redirect("/#login?error=disabled")
            user.google_id = google_id
            if not user.name:
                user.name = name

        db.session.commit()
        login_user(user, remember=True)
        logger.info(f"Google OAuth login: {email}")
        return redirect("/#dashboard")

    except Exception as e:
        logger.error(f"Google OAuth callback failed: {e}")
        return redirect("/#login")
