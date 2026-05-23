import logging
import os
import time
import threading

import pandas as pd

from models import db, Job
from config import Config

logger = logging.getLogger(__name__)


def _clean_nan(value: str) -> str:
    """Strip NaN/NaT strings that come from pandas Excel parsing."""
    if not value or value.strip().lower() in ("nan", "nat", "none", "null"):
        return ""
    return value.strip()


# ---------------------------------------------------------------------------
# CORE SYNC LOGIC
# ---------------------------------------------------------------------------
def sync_jobs_from_excel(app, trigger_rematch: bool = True):
    """
    Read the Excel report and upsert jobs into the database.

    Returns (new_count, total_count).
    """
    with app.app_context():
        excel_path = Config.EXCEL_FILE

        if not os.path.exists(excel_path):
            logger.warning(f"Excel file not found: {excel_path}")
            return 0, 0

        try:
            xl = pd.ExcelFile(excel_path)
        except Exception as e:
            logger.error(f"Cannot open Excel file: {e}")
            return 0, 0

        # Read the combined "All Active Jobs" sheet
        target_sheet = None
        for name in xl.sheet_names:
            if "all active" in name.lower():
                target_sheet = name
                break

        if not target_sheet:
            # Fallback: read all per-source sheets
            logger.info("'All Active Jobs' sheet not found, reading per-source sheets...")
            source_sheets = [s for s in xl.sheet_names
                             if s not in ("Dashboard", "Closed Jobs")
                             and "all active" not in s.lower()]
            frames = []
            for sheet_name in source_sheets:
                try:
                    df = xl.parse(sheet_name)
                    if not df.empty:
                        frames.append(df)
                except Exception:
                    pass
            if frames:
                df_all = pd.concat(frames, ignore_index=True)
            else:
                df_all = pd.DataFrame()
        else:
            df_all = xl.parse(target_sheet)

        if df_all.empty:
            logger.info("No jobs found in Excel.")
            return 0, 0

        # Normalize column names to match our model
        col_map = {
            "Job Title": "title",
            "Company / Department": "company",
            "Location": "location",
            "Source": "source",
            "Source Portal": "source",
            "Job Link": "link",
            "Date Scraped": "date_scraped",
            "Posted Date": "posted_date",
            "Deadline": "deadline",
            "Status": "status",
        }
        df_all = df_all.rename(columns=col_map)

        # Drop the row-number column if present
        if "#" in df_all.columns:
            df_all = df_all.drop(columns=["#"])

        new_count = 0
        existing_links = {j.link for j in Job.query.with_entities(Job.link).all() if j.link}
        # Also index by title+company for linkless rows
        existing_keys = {
            (j.title.strip().lower(), (j.company or "").strip().lower())
            for j in Job.query.with_entities(Job.title, Job.company).all()
            if j.title
        }

        for _, row in df_all.iterrows():
            title = _clean_nan(str(row.get("title", "")))
            if not title:
                continue

            link = _clean_nan(str(row.get("link", "")))
            company = _clean_nan(str(row.get("company", "")))

            # Deduplication
            if link and link in existing_links:
                continue
            key = (title.lower(), company.lower())
            if key in existing_keys:
                continue

            location = _clean_nan(str(row.get("location", "")))
            source = _clean_nan(str(row.get("source", "")))
            date_scraped = _clean_nan(str(row.get("date_scraped", "")))
            deadline = _clean_nan(str(row.get("deadline", "")))

            job = Job(
                title=title,
                company=company,
                location=location,
                source=source,
                link=link,
                date_scraped=date_scraped,
                deadline=deadline,
                status="Active"
            )
            db.session.add(job)
            
            if link:
                existing_links.add(link)
            existing_keys.add(key)
            new_count += 1

        db.session.commit()

        total_active = Job.query.filter_by(status="Active").count()
        logger.info(f"Job sync complete: {new_count} new, {total_active} total active.")

        # Trigger rematch if needed
        if new_count > 0 and trigger_rematch:
            try:
                from matcher import rematch_all_users
                rematch_all_users()
                
                from notifications import send_job_alerts
                send_job_alerts(app)
            except Exception as e:
                logger.error(f"Post-sync logic failed: {e}")

        return new_count, total_active


# ---------------------------------------------------------------------------
# BACKGROUND SYNC SCHEDULER (Using Threading)
# ---------------------------------------------------------------------------
def _sync_loop(app, interval_seconds: int):
    while True:
        time.sleep(interval_seconds)
        try:
            sync_jobs_from_excel(app, trigger_rematch=True)
        except Exception as e:
            logger.error(f"Background sync failed: {e}", exc_info=True)


def start_sync_thread(app, interval_seconds: int = 300):
    thread = threading.Thread(
        target=_sync_loop,
        args=(app, interval_seconds),
        daemon=True
    )
    thread.start()
    logger.info(f"Background job sync thread started (interval: {interval_seconds}s)")
    return thread
