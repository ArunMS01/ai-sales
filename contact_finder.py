"""
CONTACT FINDER
==============
Finds real contact details for IndiaMART leads using:
1. JustDial cross-reference (same business, real phone)
2. Google search for real email/website
3. Company website contact page scraper
4. WhatsApp check on existing number
"""
import os
import re
import time
import requests
from bs4 import BeautifulSoup

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html",
    "Accept-Language": "en-IN,en;q=0.9",
}


class ContactFinder:

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def find_all(self, lead):
        """
        Master method — tries all sources and returns best contacts found.
        Updates lead dict in place and returns it.
        """
        company = lead.get("company") or lead.get("name") or ""
        city    = lead.get("city") or "India"
        print("[ContactFinder] Finding contacts for: " + company)

        # Source 1: JustDial — best for Indian business real numbers
        jd = self.search_justdial(company, city)
        if jd.get("phone"):
            lead["phone"]   = jd["phone"]
            lead["email"]   = jd.get("email") or lead.get("email") or ""
            lead["website"] = jd.get("website") or lead.get("website") or ""
            print("  [JustDial] Phone: " + jd["phone"])

        # Source 2: Google search for real website + email
        if not lead.get("email") or not lead.get("website"):
            google = self.google_search_contacts(company, city)
            if google.get("email") and not lead.get("email"):
                lead["email"] = google["email"]
                print("  [Google] Email: " + google["email"])
            if google.get("website") and (not lead.get("website") or "indiamart" in lead.get("website", "")):
                lead["website"] = google["website"]
                print("  [Google] Website: " + google["website"])

        # Source 3: Scrape their real website contact page
        if lead.get("website") and "indiamart" not in lead.get("website", "") and not lead.get("email"):
            email = self.scrape_website_email(lead["website"])
            if email:
                lead["email"] = email
                print("  [Website] Email: " + email)

        # Source 4: Build WhatsApp link from any phone found
        phone = lead.get("phone", "")
        if phone:
            digits = re.sub(r'\D', '', phone)[-10:]
            if len(digits) == 10:
                lead["phone"]        = digits
                lead["whatsapp_url"] = "https://wa.me/91" + digits

        return lead

    def search_justdial(self, company, city):
        """Search JustDial for the company to get real phone number."""
        result = {"phone": "", "email": "", "website": ""}
        if not SERPAPI_KEY:
            return result
        try:
            query = company + " " + city + " site:justdial.com"
            resp  = requests.get("https://serpapi.com/search", params={
                "q":       query,
                "api_key": SERPAPI_KEY,
                "num":     3,
                "gl":      "in",
            }, timeout=10)

            if resp.status_code != 200:
                return result

            results = resp.json().get("organic_results", [])
            for r in results:
                link    = r.get("link", "")
                snippet = r.get("snippet", "")

                if "justdial.com" not in link:
                    continue

                # Extract phone from snippet
                phones = re.findall(r'[6-9]\d{9}', snippet)
                if phones:
                    result["phone"] = phones[0]

                # Try to fetch the JustDial page for more details
                try:
                    page = self.session.get(link, timeout=8)
                    if page.status_code == 200:
                        text   = re.sub(r'<[^>]+>', ' ', page.text)
                        phones = re.findall(r'[6-9]\d{9}', text)
                        emails = re.findall(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', text)
                        skip_e = ["justdial", "noreply", "example"]
                        if phones:
                            result["phone"] = phones[0]
                        for e in emails:
                            if not any(s in e for s in skip_e):
                                result["email"] = e
                                break
                        # Website link on JustDial profile
                        websites = re.findall(r'href=["\']?(https?://(?!justdial)[^\s"\'<>]+)["\']?', page.text)
                        skip_w   = ["justdial", "facebook", "twitter", "google", "youtube"]
                        for w in websites:
                            if not any(s in w for s in skip_w):
                                result["website"] = w
                                break
                except Exception:
                    pass

                if result["phone"]:
                    break

        except Exception as e:
            print("  [JustDial] Error: " + str(e)[:60])
        return result

    def google_search_contacts(self, company, city):
        """Search Google for company's real email and website."""
        result = {"phone": "", "email": "", "website": ""}
        if not SERPAPI_KEY:
            return result
        try:
            query = '"' + company + '" ' + city + ' email contact website'
            resp  = requests.get("https://serpapi.com/search", params={
                "q":       query,
                "api_key": SERPAPI_KEY,
                "num":     5,
                "gl":      "in",
            }, timeout=10)

            if resp.status_code != 200:
                return result

            data    = resp.json()
            results = data.get("organic_results", [])
            skip    = ["indiamart", "justdial", "tradeindia", "facebook",
                      "linkedin", "instagram", "quora", "wikipedia", "youtube"]

            for r in results:
                link    = r.get("link", "")
                snippet = r.get("snippet", "")

                # Extract email from snippet
                emails = re.findall(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', snippet)
                for e in emails:
                    if not any(s in e for s in ["noreply", "example"] + skip):
                        result["email"] = e
                        break

                # Real website
                if not any(s in link for s in skip) and not result["website"]:
                    result["website"] = link

                # Phone from snippet
                if not result["phone"]:
                    phones = re.findall(r'[6-9]\d{9}', snippet)
                    if phones:
                        result["phone"] = phones[0]

                if result["email"] and result["website"]:
                    break

        except Exception as e:
            print("  [Google] Error: " + str(e)[:60])
        return result

    def scrape_website_email(self, url):
        """Visit website contact/about page and extract email."""
        emails_found = []
        pages_to_try = [
            url,
            url.rstrip("/") + "/contact",
            url.rstrip("/") + "/contact-us",
            url.rstrip("/") + "/about",
        ]
        skip_e = ["noreply", "example", "privacy", "legal", "support@shopify",
                  "wordpress", "woocommerce"]
        try:
            for page_url in pages_to_try[:2]:  # only check 2 pages
                resp = self.session.get(page_url, timeout=8)
                if resp.status_code != 200:
                    continue
                text   = re.sub(r'<[^>]+>', ' ', resp.text)
                emails = re.findall(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', text)
                for e in emails:
                    if not any(s in e for s in skip_e) and len(e) < 60:
                        return e
                time.sleep(0.5)
        except Exception as e:
            print("  [Website] Scrape error: " + str(e)[:60])
        return ""


class BulkContactEnricher:
    """Runs ContactFinder on all leads in DB that are missing contacts."""

    def __init__(self):
        self.finder = ContactFinder()

    def run(self, limit=50):
        from database import init_db, load_leads, get_conn
        init_db()
        leads = load_leads(limit=limit)

        # Filter leads missing phone or email
        needs_enrichment = [
            l for l in leads
            if not l.get("email") or not l.get("phone")
        ]
        print("[BulkEnrich] " + str(len(needs_enrichment)) + " leads need contact enrichment")

        updated = 0
        for lead in needs_enrichment:
            enriched = self.finder.find_all(dict(lead))

            # Save back to DB if we found something new
            if enriched.get("phone") != lead.get("phone") or enriched.get("email") != lead.get("email"):
                try:
                    conn = get_conn()
                    cur  = conn.cursor()
                    cur.execute(
                        "UPDATE leads SET phone=%s, email=%s, website=%s, updated_at=%s WHERE id=%s",
                        (
                            enriched.get("phone") or "",
                            enriched.get("email") or "",
                            enriched.get("website") or lead.get("website") or "",
                            __import__("datetime").datetime.utcnow().isoformat(),
                            lead["id"]
                        )
                    )
                    conn.commit()
                    cur.close()
                    conn.close()
                    updated += 1
                    print("  Updated: " + lead.get("company", "") + " | phone=" + (enriched.get("phone") or "—") + " | email=" + (enriched.get("email") or "—"))
                except Exception as e:
                    print("  DB error: " + str(e))

            time.sleep(2)  # polite delay between searches

        print("[BulkEnrich] Done. Updated " + str(updated) + " leads")
        return updated
