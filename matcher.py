"""
=============================================================================
Job Matching Engine — TF-IDF + Cosine Similarity with skill/location boosts.
=============================================================================
Compares a user's parsed resume profile against all jobs in the database and
returns ranked matches with scores from 0 to 100.
=============================================================================
"""

import logging
from datetime import datetime, timezone

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from models import db, Job, Match, Profile, User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def _build_job_text(job: Job) -> str:
    """Combine job fields into a single text for vectorization."""
    parts = [
        job.title or "",
        job.company or "",
        job.location or "",
        job.requirements or "",
        job.source or "",
    ]
    return " ".join(parts).strip()


def _build_profile_text(profile: Profile) -> str:
    """Combine profile fields into a single text for vectorization."""
    parts = [
        profile.raw_text or "",
        " ".join(profile.skills),
        " ".join(profile.education),
        " ".join(profile.job_titles),
        " ".join(profile.locations),
        profile.summary or "",
    ]
    return " ".join(parts).strip()


# ---------------------------------------------------------------------------
# CORE MATCHING
# ---------------------------------------------------------------------------
def compute_matches_for_user(user_id: int, threshold: float = 0.0) -> list[dict]:
    """
    Compute match scores between a user's profile and all active jobs.
    Stores results in the Matches table and returns the ranked list.

    Parameters
    ----------
    user_id : int
        The user whose profile to match.
    threshold : float
        Minimum score (0-100) to include in results. Default 0 = return all.

    Returns
    -------
    list[dict]  — sorted by score descending, each entry has job + score.
    """
    user = db.session.get(User, user_id)
    if not user or not user.profile:
        logger.warning(f"No profile found for user {user_id}")
        return []

    profile = user.profile
    profile_text = _build_profile_text(profile)
    if not profile_text.strip():
        return []

    # Fetch all active jobs
    jobs = Job.query.filter_by(status="Active").all()
    if not jobs:
        logger.info("No active jobs in database to match against.")
        return []

    # Build corpus: index 0 = profile, index 1..N = jobs
    corpus = [profile_text] + [_build_job_text(j) for j in jobs]

    # TF-IDF Vectorization
    try:
        vectorizer = TfidfVectorizer(
            stop_words="english",
            max_features=5000,
            ngram_range=(1, 2),
            min_df=1,
        )
        tfidf_matrix = vectorizer.fit_transform(corpus)
    except ValueError:
        logger.warning("TF-IDF failed (possibly empty vocabulary)")
        return []

    # Cosine similarity: profile vs each job
    profile_vector = tfidf_matrix[0:1]
    job_vectors = tfidf_matrix[1:]
    similarities = cosine_similarity(profile_vector, job_vectors).flatten()

    # ---------- Boosting ----------
    profile_skills = {s.lower() for s in profile.skills}
    profile_locations = {loc.lower() for loc in profile.locations}
    profile_titles = {t.lower() for t in profile.job_titles}

    boosted_scores = []
    for idx, job in enumerate(jobs):
        base_score = float(similarities[idx])

        # Skill boost: +3% per matching skill (max +30%)
        job_text_lower = _build_job_text(job).lower()
        skill_hits = sum(1 for s in profile_skills if s in job_text_lower)
        skill_boost = min(skill_hits * 0.03, 0.30)

        # Location boost: +10% if location matches
        location_boost = 0.0
        if profile_locations:
            job_loc_lower = (job.location or "").lower()
            if any(loc in job_loc_lower for loc in profile_locations):
                location_boost = 0.10

        # Title boost: +15% if job title contains a title from profile
        title_boost = 0.0
        job_title_lower = (job.title or "").lower()
        if any(t in job_title_lower for t in profile_titles):
            title_boost = 0.15

        # Combine: base + boosts, capped at 1.0
        final = min(base_score + skill_boost + location_boost + title_boost, 1.0)
        final_pct = round(final * 100, 1)

        boosted_scores.append((job, final_pct))

    # Sort by score descending
    boosted_scores.sort(key=lambda x: x[1], reverse=True)

    # Filter by threshold
    results = [(job, score) for job, score in boosted_scores if score >= threshold]

    # ---------- Persist to database ----------
    try:
        # Delete old matches for this user
        Match.query.filter_by(user_id=user_id).delete()

        for job, score in results:
            match = Match(
                user_id=user_id,
                job_id=job.id,
                score=score,
            )
            db.session.add(match)

        db.session.commit()
        logger.info(f"Stored {len(results)} matches for user {user_id}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to store matches: {e}")

    return [
        {
            "score": score,
            "job": job.to_dict(),
        }
        for job, score in results
    ]


def rematch_all_users(threshold: float = 0.0):
    """
    Re-compute matches for every user that has a profile.
    Called when new jobs are synced from the Excel file.
    """
    users_with_profiles = User.query.join(Profile).all()
    logger.info(f"Re-matching {len(users_with_profiles)} users with profiles...")

    for user in users_with_profiles:
        try:
            compute_matches_for_user(user.id, threshold)
        except Exception as e:
            logger.error(f"Re-match failed for user {user.id}: {e}")

    return len(users_with_profiles)
