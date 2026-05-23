"""Quick diagnostic: check what Rozee.pk and FPSC pages actually contain."""
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
        ignore_https_errors=True
    )
    page = ctx.new_page()

    # ---- ROZEE.PK ----
    print("=" * 60)
    print("ROZEE.PK DIAGNOSIS")
    print("=" * 60)
    page.goto("https://www.rozee.pk/job/jsearch/q/all", timeout=60000)
    page.wait_for_timeout(5000)
    for _ in range(5):
        page.evaluate("window.scrollBy(0, 800)")
        page.wait_for_timeout(800)
    html = page.content()
    soup = BeautifulSoup(html, "html.parser")

    # Check CSS classes with "job" in them
    classes = set()
    for d in soup.find_all("div", class_=True):
        for c in d.get("class", []):
            if "job" in c.lower():
                classes.add(c)
    print(f"Job-related CSS classes: {sorted(classes)}")

    # Check links with /job/ in href
    links = [a for a in soup.find_all("a", href=True)
             if "/job/" in a.get("href", "") and len(a.get_text(strip=True)) > 4]
    print(f"Links with /job/ in href: {len(links)}")
    for link in links[:5]:
        title = link.get_text(strip=True)[:70]
        href = link.get("href", "")[:80]
        print(f"  Title: {title}")
        print(f"  Href:  {href}")
        print()

    # ---- FPSC ----
    print("=" * 60)
    print("FPSC DIAGNOSIS")
    print("=" * 60)
    page.goto("https://www.fpsc.gov.pk/Jobs?section=GR", timeout=60000)
    page.wait_for_timeout(5000)
    html = page.content()
    soup = BeautifulSoup(html, "html.parser")

    h2s = soup.find_all("h2")
    print(f"H2 elements: {len(h2s)}")
    for h2 in h2s[:5]:
        print(f"  H2: {h2.get_text(strip=True)[:80]}")

    links = soup.find_all("a", href=True)
    job_links = [a for a in links if "job" in a.get("href", "").lower() or "view" in a.get("href", "").lower()]
    print(f"Job-looking links: {len(job_links)}")
    for a in job_links[:5]:
        print(f"  {a.get_text(strip=True)[:60]} -> {a['href'][:80]}")

    # ---- AJKPSC (with ignore_https_errors) ----
    print("=" * 60)
    print("AJKPSC DIAGNOSIS")
    print("=" * 60)
    try:
        page.goto("https://www.ajkpsc.gov.pk/home/default.asp", timeout=60000)
        page.wait_for_timeout(5000)
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        links = [a for a in soup.find_all("a", href=True)
                 if any(x in a.get_text(strip=True).lower() for x in ["adv", "vacancy", "job", "recruit"])]
        print(f"Advertisement links: {len(links)}")
        for a in links[:5]:
            print(f"  {a.get_text(strip=True)[:60]}")
    except Exception as e:
        print(f"AJKPSC failed: {e}")

    browser.close()
    print("\nDone.")
