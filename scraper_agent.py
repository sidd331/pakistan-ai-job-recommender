"""
=============================================================================
Pakistan Job AI Scraper Agent - Main Entry Point
=============================================================================
Schedules and runs the full scraping cycle every 6 hours.
Outputs a professionally formatted Excel report.

Usage:
    python scraper_agent.py

The terminal must stay open for the 6-hour scheduler to work.
=============================================================================
"""

import logging
import sys
import os

# Force UTF-8 output in Windows terminal to support special characters
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import time
import schedule
from datetime import datetime

from extractors import run_all_extractors
from data_manager import update_excel, EXCEL_FILE

# ---------------------------------------------------------------------------
# LOGGING SETUP
# ---------------------------------------------------------------------------
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

log_filename = os.path.join(log_dir, f"agent_{datetime.now().strftime('%Y%m%d')}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)-8s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_filename, encoding="utf-8"),
    ]
)
logger = logging.getLogger(__name__)

BANNER = """
+==================================================================+
|      [PK]  Pakistan Job Market AI Scraper Agent                  |
|------------------------------------------------------------------|
|  Sources  :  Rozee.pk | Mustakbil | FPSC | KPPSC | SPSC | AJKPSC|
|------------------------------------------------------------------|
|  Schedule :  Every 6 hours (runs immediately on start)           |
|  Output   :  Pakistan_Jobs_Report.xlsx  (auto-updated)           |
+==================================================================+
"""

# ---------------------------------------------------------------------------
# SCRAPING TASK
# ---------------------------------------------------------------------------
def run_scraping_cycle():
    start_time = datetime.now()
    logger.info("=" * 70)
    logger.info(f"[START] SCRAPING CYCLE STARTED  --  {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 70)

    try:
        # Step 1: Scrape all sites
        logger.info("Step 1/2 — Scraping all job portals...")
        all_jobs = run_all_extractors()

        # Step 2: Write to Excel
        logger.info("Step 2/2 — Generating professional Excel report...")
        total_active, stats = update_excel(all_jobs)

        # Summary printout
        elapsed = (datetime.now() - start_time).seconds
        logger.info("=" * 70)
        logger.info("[DONE] SCRAPING CYCLE COMPLETE")
        logger.info(f"   Duration  : {elapsed}s")
        logger.info(f"   Total Active Jobs Found : {total_active}")
        logger.info(f"   Report saved to         : {os.path.abspath(EXCEL_FILE)}")
        logger.info("")
        logger.info("   Breakdown by Source:")
        for source, data in stats.items():
            active = data.get("active", 0)
            closed = data.get("closed", 0)
            bar = "|" * min(active, 30) if active else "(none)"
            logger.info(f"     {source:18s}: {active:4d} active   {closed:3d} closed   {bar}")
        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"[ERROR] SCRAPING CYCLE FAILED: {e}", exc_info=True)

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    print(BANNER)
    logger.info("Agent initializing...")
    logger.info(f"Log file: {os.path.abspath(log_filename)}")

    # Run immediately on start
    run_scraping_cycle()

    # Schedule every 6 hours
    schedule.every(6).hours.do(run_scraping_cycle)
    next_run = schedule.next_run()
    logger.info(f"[TIMER] Next scheduled run: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("Agent is running. Keep this terminal open. Press Ctrl+C to stop.\n")

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)  # Check every 30 seconds
    except KeyboardInterrupt:
        logger.info("\n[STOP] Agent stopped by user. Goodbye!")
        sys.exit(0)

if __name__ == "__main__":
    main()
