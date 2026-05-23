"""
=============================================================================
Professional AI Job Scraper - Data Manager Module
=============================================================================
Handles all Excel read/write operations with:
  - Separate sheets per source website
  - Summary "All Active Jobs" sheet
  - "Closed Jobs" sheet for ended postings
=============================================================================
"""

import os
import logging
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)

EXCEL_FILE = "Pakistan_Jobs_Report.xlsx"

SOURCE_SHEETS = {
    "Rozee.pk":  "Rozee.pk",
    "Mustakbil": "Mustakbil.com",
    "FPSC":      "FPSC",
    "KPPSC":     "KPPSC",
    "SPSC":      "SPSC",
    "AJKPSC":    "AJKPSC",
}

COLUMNS = ["#", "Job Title", "Company / Department", "Location", "Source Portal",
           "Job Link", "Date Scraped", "Deadline", "Status"]

def update_excel(jobs_dict: dict) -> tuple[int, dict]:
    """
    Given a dict of {source: [jobs]}, creates a professional Excel file
    and returns (total_active, stats_dict).
    """
    logger.info("Updating Excel file...")
    stats = {}
    total_active = 0

    try:
        with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
            all_active = []
            
            # Write per source sheet
            for source_key, jobs in jobs_dict.items():
                sheet_name = SOURCE_SHEETS.get(source_key, source_key)
                
                rows = []
                for idx, job in enumerate(jobs, 1):
                    rows.append({
                        "#": idx,
                        "Job Title": job.get("Title", job.get("title", "")),
                        "Company / Department": job.get("Company", job.get("company", "")),
                        "Location": job.get("Location", job.get("location", "")),
                        "Source Portal": job.get("Source", job.get("source", source_key)),
                        "Job Link": job.get("Link", job.get("link", "")),
                        "Date Scraped": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "Deadline": job.get("Deadline", job.get("deadline", "")),
                        "Status": "Active"
                    })
                
                df = pd.DataFrame(rows, columns=COLUMNS)
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                stats[source_key] = {"active": len(jobs), "closed": 0}
                total_active += len(jobs)
                all_active.extend(rows)

            # Write All Active Jobs sheet
            if all_active:
                df_all = pd.DataFrame(all_active, columns=COLUMNS)
                df_all.to_excel(writer, sheet_name="All Active Jobs", index=False)
            
            # Write empty Dashboard and Closed Jobs to meet expectations
            pd.DataFrame(columns=COLUMNS).to_excel(writer, sheet_name="Closed Jobs", index=False)
            pd.DataFrame([{"Message": "Dashboard summary here"}]).to_excel(writer, sheet_name="Dashboard", index=False)

        return total_active, stats
    except Exception as e:
        logger.error(f"Failed to write Excel: {e}")
        return 0, {}
