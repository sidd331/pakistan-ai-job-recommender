"""
=============================================================================
Professional AI Job Scraper - Extractors Module
=============================================================================
Site-specific extraction logic for 6 Pakistani job portals.
Uses Playwright for JS-rendered sites and BeautifulSoup for HTML parsing.
=============================================================================
"""

from playwright.sync_api import sync_playwright, Page
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)

# ===========================================================================
# ROZEE.PK EXTRACTOR
# URL: https://www.rozee.pk/job/jsearch/q/all
# Structure: div.job-box > h3 > a (title), div > bdi > a.display-inline (company)
# ===========================================================================
def scrape_rozee(page: Page) -> list[dict]:
    source = "Rozee.pk"
    jobs = []
    seen_links = set()
    max_pages = 5  # scrape up to 5 pages

    try:
        for page_num in range(1, max_pages + 1):
            # Rozee.pk uses /fp/<page_num> for pagination (fp = first page offset)
            url = f"https://www.rozee.pk/job/jsearch/q/all/fp/{page_num}"
            logger.info(f"[{source}] Loading page {page_num}: {url}")
            page.goto(url, timeout=60000)
            page.wait_for_timeout(4000)

            # Scroll down to trigger lazy-loading
            for _ in range(5):
                page.evaluate("window.scrollBy(0, 800)")
                page.wait_for_timeout(800)

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            base = "https://www.rozee.pk"

            # Job cards on Rozee — multiple possible selectors
            job_boxes = soup.select("div.job, li.job, div[class*='job-listing'], div.job-box, div[class*='job-card']")
            logger.info(f"[{source}] Page {page_num}: Found {len(job_boxes)} potential containers")

            if not job_boxes:
                # Fallback: scan all anchors pointing to /job/ urls
                all_links = soup.find_all("a", href=True)
                job_boxes = [a.find_parent("div") or a for a in all_links
                             if "/job/" in a.get("href", "") and a.get_text(strip=True)]

            if not job_boxes:
                logger.info(f"[{source}] No more job containers on page {page_num}, stopping.")
                break

            page_jobs = 0
            for box in job_boxes:
                # Find title link — job titles are typically in <h3><a> or just <a> links
                title_tag = box.find("h3") or box.find("h2") or box
                link_tag = title_tag.find("a", href=True) if title_tag else None

                if not link_tag:
                    link_tag = box.find("a", href=True)

                if not link_tag:
                    continue

                title = link_tag.get_text(strip=True)
                href = link_tag.get("href", "")

                if not title or not href or len(title) < 4:
                    continue

                # Only take actual job links, not category/filter links
                if not any(x in href for x in ['/job/', '/jobs/']):
                    continue

                full_link = urljoin(base, href) if href.startswith('/') else href

                if full_link in seen_links:
                    continue
                seen_links.add(full_link)

                # Find company name and location
                company = ""
                location = "Pakistan"

                parent = link_tag.find_parent("div") or link_tag.find_parent("li")
                if parent:
                    # Company is often in a <bdi> or .display-inline
                    company_tag = parent.select_one("a.display-inline, [class*='company']")
                    if company_tag:
                        company = company_tag.get_text(strip=True)

                    # Location is often in a <bdi> with a city name
                    bdi_tags = parent.find_all("bdi")
                    for bdi in bdi_tags:
                        text = bdi.get_text(strip=True)
                        if any(city in text for city in ["Karachi", "Lahore", "Islamabad",
                                "Rawalpindi", "Peshawar", "Multan", "Faisalabad",
                                "Quetta", "Hyderabad", "Pakistan", ","]):
                            location = text
                            break

                    # Also try dedicated location spans
                    loc_tag = parent.select_one("[class*='location']")
                    if loc_tag:
                        location = loc_tag.get_text(strip=True)

                jobs.append({
                    "Title": title,
                    "Company": company or "N/A",
                    "Location": location,
                    "Source": source,
                    "Link": full_link,
                    "Posted Date": "",
                    "Deadline": "",
                    "Status": "Active"
                })
                page_jobs += 1

            logger.info(f"[{source}] Page {page_num}: {page_jobs} new jobs")

            if page_jobs == 0:
                logger.info(f"[{source}] Empty page {page_num}, stopping pagination.")
                break

        logger.info(f"[{source}] Total extracted: {len(jobs)} jobs across {min(page_num, max_pages)} pages")
    except Exception as e:
        logger.error(f"[{source}] Scraping failed: {e}")

    return jobs


# ===========================================================================
# MUSTAKBIL.COM EXTRACTOR
# URL: https://www.mustakbil.com/jobs
# Structure: article > a.job-title__link, span (company), span (location)
# ===========================================================================
def scrape_mustakbil(page: Page) -> list[dict]:
    source = "Mustakbil.com"
    jobs = []
    seen_links = set()
    max_pages = 5  # scrape up to 5 pages

    try:
        for page_num in range(1, max_pages + 1):
            url = f"https://www.mustakbil.com/jobs?page={page_num}"
            logger.info(f"[{source}] Loading page {page_num}: {url}")
            page.goto(url, timeout=60000)
            page.wait_for_timeout(3000)

            # Scroll to trigger lazy loading
            for _ in range(3):
                page.evaluate("window.scrollBy(0, 600)")
                page.wait_for_timeout(800)

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            base = "https://www.mustakbil.com"

            # Job listings are in <article> elements on Mustakbil
            articles = soup.find_all("article")
            if not articles:
                # Fallback: scan for any job-title links
                articles = soup.select("[class*='job']")

            if not articles:
                logger.info(f"[{source}] No more articles found on page {page_num}, stopping.")
                break

            page_jobs = 0
            for article in articles:
                # Title link: a[class*='job-title'] or any prominent link
                title_tag = (article.select_one("a[class*='job-title']") or
                             article.select_one("a[class*='title']") or
                             article.find("h2") or
                             article.find("h3"))

                if not title_tag:
                    continue

                # If it's not an anchor, find the first anchor inside
                if title_tag.name != "a":
                    title_tag = title_tag.find("a") or title_tag

                title = title_tag.get_text(strip=True)
                href = title_tag.get("href", "") if title_tag.name == "a" else ""

                if not title or len(title) < 4:
                    continue

                full_link = urljoin(base, href) if href else ""

                if not full_link or full_link in seen_links or full_link == base:
                    continue
                seen_links.add(full_link)

                # Company and location
                company = ""
                location = "Pakistan"

                # Try to find company and location from spans
                spans = article.find_all("span")
                if len(spans) >= 1:
                    company = spans[0].get_text(strip=True)
                if len(spans) >= 2:
                    loc_text = spans[1].get_text(strip=True)
                    if loc_text:
                        location = loc_text

                # Also try dedicated class selectors
                company_tag = article.select_one("[class*='company']")
                if company_tag:
                    company = company_tag.get_text(strip=True)
                location_tag = article.select_one("[class*='location']")
                if location_tag:
                    location = location_tag.get_text(strip=True)

                jobs.append({
                    "Title": title,
                    "Company": company or "N/A",
                    "Location": location,
                    "Source": source,
                    "Link": full_link,
                    "Posted Date": "",
                    "Deadline": "",
                    "Status": "Active"
                })
                page_jobs += 1

            logger.info(f"[{source}] Page {page_num}: {page_jobs} new jobs")

            if page_jobs == 0:
                logger.info(f"[{source}] Empty page {page_num}, stopping pagination.")
                break

        logger.info(f"[{source}] Total extracted: {len(jobs)} jobs across {min(page_num, max_pages)} pages")
    except Exception as e:
        logger.error(f"[{source}] Scraping failed: {e}")

    return jobs


# ===========================================================================
# FPSC EXTRACTOR (Federal Public Service Commission)
# URL: https://www.fpsc.gov.pk/Jobs?section=GR
# Structure: Card-based grid (Tailwind CSS), h2 for title, <p> for date
# ===========================================================================
def scrape_fpsc(page: Page) -> list[dict]:
    source = "FPSC"
    jobs = []
    try:
        logger.info(f"[{source}] Navigating to advertisements page...")
        page.goto("https://www.fpsc.gov.pk/Jobs?section=GR", timeout=60000)
        page.wait_for_timeout(4000)

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        base = "https://www.fpsc.gov.pk"

        # FPSC uses card-based layout: each card has an h2 title and link to /Job_view
        cards = soup.find_all("h2")
        logger.info(f"[{source}] Found {len(cards)} h2 elements to check")

        seen_links = set()
        for h2 in cards:
            title = h2.get_text(strip=True)
            if not title or len(title) < 6:
                continue

            # Look for the link in nearby elements
            parent = h2.find_parent("div") or h2.find_parent("article") or h2.find_parent("section")
            link_tag = None
            posted_date = ""

            if parent:
                link_tag = parent.find("a", href=True)
                # Posted date usually in a <p> tag
                p_tags = parent.find_all("p")
                for p in p_tags:
                    text = p.get_text(strip=True)
                    if re.search(r'\d{4}', text):  # Contains a year => date
                        posted_date = text
                        break

            href = link_tag.get("href", "") if link_tag else ""
            full_link = urljoin(base, href) if href else base + "/Jobs?section=GR"

            if full_link in seen_links:
                continue
            seen_links.add(full_link)

            jobs.append({
                "Title": title,
                "Company": "Federal Public Service Commission (FPSC)",
                "Location": "Pakistan (Federal)",
                "Source": source,
                "Link": full_link,
                "Posted Date": posted_date,
                "Deadline": "",
                "Status": "Active"
            })

        logger.info(f"[{source}] Extracted {len(jobs)} jobs")
    except Exception as e:
        logger.error(f"[{source}] Scraping failed: {e}")
    
    return jobs


# ===========================================================================
# KPPSC EXTRACTOR (Khyber Pakhtunkhwa Public Service Commission)
# URL: https://www.kppsc.gov.pk/advertisement
# Structure: Table-based with advertisement titles and date posted
# ===========================================================================
def scrape_kppsc(page: Page) -> list[dict]:
    source = "KPPSC"
    jobs = []
    try:
        logger.info(f"[{source}] Navigating to advertisements page...")
        page.goto("https://www.kppsc.gov.pk/advertisement", timeout=60000)
        page.wait_for_timeout(4000)

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        base = "https://www.kppsc.gov.pk"

        seen_links = set()

        # KPPSC lists advertisements as linked items in a section
        # Look for links pointing to PDF or advertisement pages
        all_links = soup.find_all("a", href=True)
        
        for a in all_links:
            href = a.get("href", "")
            text = a.get_text(strip=True)
            
            # Filter for valid advertisement links
            if not text or len(text) < 10:
                continue
            
            # KPPSC advertisements contain "ADVERTISEMENT" or "Adv" or "No." in title
            text_upper = text.upper()
            if not any(x in text_upper for x in ["ADVERTISEMENT", "ADV", "NOTICE", "CIRCULAR", "RECRUITMENT", "PMS", "CIVIL JUDGE"]):
                continue
            
            full_link = urljoin(base, href)
            if full_link in seen_links:
                continue
            seen_links.add(full_link)

            # Try to find a date near this link
            posted_date = ""
            parent = a.find_parent("div") or a.find_parent("li") or a.find_parent("td")
            if parent:
                # Look for sibling or child text that looks like a date
                text_nodes = parent.find_all(string=re.compile(r'\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4}'))
                if text_nodes:
                    posted_date = text_nodes[0].strip()

            jobs.append({
                "Title": text,
                "Company": "Khyber Pakhtunkhwa PSC (KPPSC)",
                "Location": "Khyber Pakhtunkhwa",
                "Source": source,
                "Link": full_link,
                "Posted Date": posted_date,
                "Deadline": "",
                "Status": "Active"
            })

        logger.info(f"[{source}] Extracted {len(jobs)} jobs")
    except Exception as e:
        logger.error(f"[{source}] Scraping failed: {e}")
    
    return jobs


# ===========================================================================
# SPSC EXTRACTOR (Sindh Public Service Commission)
# URL: https://spsc.gov.pk/advertisement.php
# Structure: Section with accordion-style panels, title in h3 links
# Status filtering: Only pick advertisements NOT labeled "Closed"
# ===========================================================================
def scrape_spsc(page: Page) -> list[dict]:
    source = "SPSC"
    jobs = []
    try:
        logger.info(f"[{source}] Navigating to advertisements page...")
        page.goto("https://spsc.gov.pk/advertisement.php", timeout=60000)
        page.wait_for_timeout(4000)

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        base = "https://spsc.gov.pk"

        seen_links = set()

        # SPSC advertisements are h3 tags with links - closed ones include "Closed" in their text
        headings = soup.find_all(["h3", "h4"])
        
        for heading in headings:
            a_tag = heading.find("a", href=True)
            if not a_tag:
                continue
            
            text = heading.get_text(strip=True)
            href = a_tag.get("href", "")
            
            if not text or len(text) < 5:
                continue
            
            # Skip advertisements explicitly marked as "Closed"
            if "closed" in text.lower():
                continue
            
            full_link = urljoin(base, href)
            if full_link in seen_links:
                continue
            seen_links.add(full_link)

            # Extract deadline from title text (common pattern: "Closing dt:DD.MM.YY")
            deadline = ""
            deadline_match = re.search(r'[Cc]losing\s+(?:dt|date|Date)?[:\s]*([\d./-]+)', text)
            if deadline_match:
                deadline = deadline_match.group(1)

            jobs.append({
                "Title": text,
                "Company": "Sindh Public Service Commission (SPSC)",
                "Location": "Sindh",
                "Source": source,
                "Link": full_link,
                "Posted Date": "",
                "Deadline": deadline,
                "Status": "Active"
            })

        logger.info(f"[{source}] Extracted {len(jobs)} active jobs")
    except Exception as e:
        logger.error(f"[{source}] Scraping failed: {e}")
    
    return jobs


# ===========================================================================
# AJKPSC EXTRACTOR (AJ&K Public Service Commission)
# URL: https://www.ajkpsc.gov.pk/home/default.asp
# Structure: News section lists advertisement titles as links
# ===========================================================================
def scrape_ajkpsc(page: Page) -> list[dict]:
    source = "AJKPSC"
    jobs = []
    try:
        logger.info(f"[{source}] Navigating to home page for advertisement links...")
        page.goto("https://www.ajkpsc.gov.pk/home/default.asp", timeout=60000)
        page.wait_for_timeout(4000)

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        base = "https://www.ajkpsc.gov.pk"

        seen_links = set()
        
        # AJKPSC posts advertisements in a news/updates section
        # Advertisement links typically contain "Advertisement" or "adv" or "Vacancy"
        all_links = soup.find_all("a", href=True)
        
        for a in all_links:
            text = a.get_text(strip=True)
            href = a.get("href", "")
            
            if not text or len(text) < 6:
                continue
            
            text_lower = text.lower()
            href_lower = href.lower()
            
            # Match advertisement-type links
            is_advert = any(x in text_lower for x in ["advertisement", "vacancy", "vacancies", "recruit", "job"])
            is_advert_link = any(x in href_lower for x in ["adv", "advertisement", "vacancy", "oas"])
            
            if not (is_advert or is_advert_link):
                continue
            
            # Skip navigation links and non-content ones
            if any(x in href_lower for x in ["#", "javascript:", "contact", "about", "result"]):
                continue
            
            full_link = urljoin(base, href) if not href.startswith("http") else href
            if full_link in seen_links:
                continue
            seen_links.add(full_link)

            jobs.append({
                "Title": text,
                "Company": "AJ&K Public Service Commission (AJKPSC)",
                "Location": "Azad Jammu & Kashmir",
                "Source": source,
                "Link": full_link,
                "Posted Date": "",
                "Deadline": "",
                "Status": "Active"
            })

        logger.info(f"[{source}] Extracted {len(jobs)} jobs")
    except Exception as e:
        logger.error(f"[{source}] Scraping failed: {e}")
    
    return jobs


# ===========================================================================
# CUSTOM SOURCES EXTRACTOR (Generic HTML Scraper)
# Scrapes URLs added by admins in the Admin Panel
# ===========================================================================
def scrape_custom_sources(page: Page) -> list[dict]:
    source_label = "Custom Sources"
    jobs = []
    
    # Needs to connect to DB directly since this runs outside Flask request context
    try:
        from app import create_app
        from models import CustomSource
        app = create_app()
        with app.app_context():
            custom_sources = CustomSource.query.all()
    except Exception as e:
        logger.error(f"[{source_label}] Failed to connect to DB to get sources: {e}")
        return []

    if not custom_sources:
        logger.info(f"[{source_label}] No custom sources configured.")
        return []

    for src in custom_sources:
        seen_links = set()
        logger.info(f"[{source_label}] Scraping {src.name} at {src.url}...")
        try:
            page.goto(src.url, timeout=60000)
            page.wait_for_timeout(3000)

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            
            # Simple generic parsing: look for prominent links with job-related keywords
            for a in soup.find_all("a", href=True):
                text = a.get_text(strip=True)
                href = a.get("href", "")
                
                # Minimum length for a job title and containing job keywords
                if len(text) > 8 and any(k in text.lower() for k in ["job", "hiring", "career", "manager", "developer", "engineer", "officer", "specialist"]):
                    full_link = urljoin(src.url, href) if not href.startswith("http") else href
                    
                    if full_link in seen_links:
                        continue
                    seen_links.add(full_link)

                    jobs.append({
                        "Title": text[:150], # Limit length
                        "Company": src.name,
                        "Location": "Pakistan",
                        "Source": f"Custom - {src.name}",
                        "Link": full_link,
                        "Posted Date": "",
                        "Deadline": "",
                        "Status": "Active"
                    })
        except Exception as e:
            logger.error(f"[{source_label}] Failed to scrape {src.name}: {e}")

    logger.info(f"[{source_label}] Extracted {len(jobs)} jobs from custom sources")
    return jobs


# ===========================================================================
# MASTER RUNNER
# ===========================================================================
def run_all_extractors() -> dict[str, list[dict]]:
    """
    Launches a single Playwright browser, runs all 6 scrapers sequentially,
    and returns a dictionary mapping source names to their job lists.
    """
    all_jobs = {}

    with sync_playwright() as p:
        logger.info("Launching headless browser...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="en-US"
        )
        page = context.new_page()

        scrapers = [
            ("Rozee.pk",    scrape_rozee),
            ("Mustakbil",   scrape_mustakbil),
            ("FPSC",        scrape_fpsc),
            ("KPPSC",       scrape_kppsc),
            ("SPSC",        scrape_spsc),
            ("AJKPSC",      scrape_ajkpsc),
            ("Custom",      scrape_custom_sources),
        ]

        for name, scraper_fn in scrapers:
            try:
                logger.info(f"--- Starting scraper: {name} ---")
                jobs = scraper_fn(page)
                all_jobs[name] = jobs
                logger.info(f"--- {name} done: {len(jobs)} jobs found ---")
            except Exception as e:
                logger.error(f"--- {name} FAILED: {e} ---")
                all_jobs[name] = []

        browser.close()
        logger.info("Browser closed.")

    return all_jobs


if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    results = run_all_extractors()
    print("\n" + "="*60)
    print("SCRAPING SUMMARY")
    print("="*60)
    for source, jobs in results.items():
        print(f"  {source:20s}: {len(jobs):3d} jobs found")
    print("="*60)
