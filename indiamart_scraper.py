import os
import re
import json
import time
import requests
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")

# ── Customizable Search Config ────────────────────────────────────────────────
# Edit CATEGORIES and CITIES to target any niche + location
CATEGORIES = {
    "Chemicals": [
        "chemical manufacturer kanpur",
        "chemical supplier kanpur india",
        "industrial chemical kanpur",
        "chemical exporter kanpur uttar pradesh",
        "agrochemical manufacturer kanpur",
        "paint chemical manufacturer kanpur",
        "cleaning chemical supplier kanpur",
        "pharmaceutical chemical kanpur",
    ],
}
TARGET_CITY = "Kanpur"

PAIN_POINTS = {
    "Chemicals": [
        "only listed on IndiaMART — invisible on Google Search",
        "no professional website — losing B2B buyers to competitors",
        "buyers can't find product specs or MSDS sheets online",
        "no online inquiry form — missing inbound leads daily",
        "competitors with websites rank above them on Google",
    ],
}


@dataclass
class IndiaMartLead:
    name: str
    website: str
    phone: str
    email: str
    city: str
    source: str = "indiamart"
    linkedin_url: str = ""
    job_title: str = "Owner / Proprietor"
    company: str = ""
    category: str = ""
    indiamart_url: str = ""
    products: str = ""
    seo_score: Optional[int] = None
    pagespeed_score: Optional[int] = None
    pain_points: list = None
    followers: int = 0
    stage: str = "new"
    created_at: str = ""

    def __post_init__(self):
        if self.pain_points is None:
            self.pain_points = []
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()


class ContactEnricher:
    """
    Visits the actual IndiaMART seller profile page and
    extracts real phone numbers and emails from the page HTML.
    """
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-IN,en;q=0.9",
    }

    def enrich(self, indiamart_url):
        result = {"phone": "", "email": "", "owner": "", "company": "", "city": ""}
        if not indiamart_url or "indiamart.com" not in indiamart_url:
            return result
        try:
            resp = requests.get(indiamart_url, headers=self.HEADERS, timeout=12)
            if resp.status_code != 200:
                return result
            html  = resp.text
            text  = re.sub(r'<[^>]+>', ' ', html)  # strip HTML tags

            # ── Real phone numbers ────────────────────────────────────────────
            # IndiaMART shows numbers in formats: +91-XXXXXXXXXX, 0XXXXXXXXXX, XXXXXXXXXX
            phones = re.findall(r'(?:\+91[\s-]?|0)?[6-9]\d{9}', text)
            # Filter out IndiaMART's own support numbers
            skip_phones = ["9696969696", "8888888888", "1800"]
            for p in phones:
                digits = re.sub(r'\D', '', p)[-10:]
                if digits and digits not in skip_phones and digits[:4] not in ["1800"]:
                    result["phone"] = digits
                    break

            # ── Real emails ───────────────────────────────────────────────────
            emails = re.findall(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', text)
            skip_emails = ["indiamart", "example", "noreply", "support", "info@ind",
                          "care@", "help@", "admin@ind", "b2b@"]
            for e in emails:
                if not any(s in e.lower() for s in skip_emails) and len(e) < 60:
                    result["email"] = e
                    break

            # ── Owner/contact name ────────────────────────────────────────────
            for pattern in [
                r'Contact Person[:\s]+([A-Z][a-zA-Z\s]{3,30})',
                r'Mr\.\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
                r'Ms\.\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
                r'Mrs\.\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
                r'Proprietor[:\s]+([A-Z][a-zA-Z\s]{3,25})',
            ]:
                m = re.search(pattern, html)
                if m:
                    result["owner"] = m.group(1).strip()
                    break

            # ── Company name ──────────────────────────────────────────────────
            company_match = re.search(r'<title[^>]*>([^<|–-]+)', html)
            if company_match:
                result["company"] = company_match.group(1).strip()[:80]

            # ── City verification ─────────────────────────────────────────────
            if "kanpur" in text.lower():
                result["city"] = "Kanpur"
            else:
                cities = ["Mumbai","Delhi","Bangalore","Hyderabad","Chennai",
                         "Kolkata","Pune","Ahmedabad","Surat","Jaipur","Lucknow",
                         "Noida","Gurugram","Indore","Agra","Varanasi","Allahabad"]
                for c in cities:
                    if c.lower() in text.lower():
                        result["city"] = c
                        break

        except Exception as e:
            print("[Enricher] Error for " + indiamart_url[:60] + ": " + str(e))
        return result


class SerpAPISource:
    BASE_URL = "https://serpapi.com/search"

    def search(self, query, num=10):
        if not SERPAPI_KEY:
            print("[SerpAPI] No SERPAPI_KEY set")
            return []
        try:
            resp = requests.get(self.BASE_URL, params={
                "q":       "site:indiamart.com " + query,
                "api_key": SERPAPI_KEY,
                "num":     num,
                "hl":      "en",
                "gl":      "in",
            }, timeout=15)

            if resp.status_code != 200:
                print("[SerpAPI] Error " + str(resp.status_code))
                return []

            results = resp.json().get("organic_results", [])
            print("[SerpAPI] '" + query + "' → " + str(len(results)) + " results")
            return results

        except Exception as e:
            print("[SerpAPI] Exception: " + str(e))
            return []


class IndiaMartLeadPipeline:

    def __init__(self):
        self.serp     = SerpAPISource()
        self.enricher = ContactEnricher()

    def clear_old_leads(self):
        """Delete all existing leads from DB for a fresh start."""
        try:
            from database import get_conn
            conn = get_conn()
            cur  = conn.cursor()
            cur.execute("DELETE FROM leads")
            conn.commit()
            count = cur.rowcount
            cur.close()
            conn.close()
            print("[DB] Cleared " + str(count) + " old leads")
        except Exception as e:
            print("[DB] Clear error: " + str(e))

    def run(self, max_per_category=25, clear_first=True):
        if clear_first:
            print("=== Clearing old leads ===")
            self.clear_old_leads()

        all_leads = []
        seen      = set()

        for category, queries in CATEGORIES.items():
            print("\n=== Category: " + category + " | City: " + TARGET_CITY + " ===")
            cat_leads = []

            for query in queries:
                if len(cat_leads) >= max_per_category:
                    break

                results = self.serp.search(query, num=10)

                for r in results:
                    title        = r.get("title", "").strip()
                    link         = r.get("link", "")
                    snippet      = r.get("snippet", "")
                    displayed    = r.get("displayed_link", "")

                    if not link or "indiamart.com" not in link:
                        continue

                    # Skip IndiaMART homepage / category pages — want seller pages only
                    if link in ["https://www.indiamart.com/", "https://dir.indiamart.com/"]:
                        continue
                    if title in seen:
                        continue
                    seen.add(title)

                    # Extract what we can from snippet immediately
                    phones  = re.findall(r'[6-9]\d{9}', snippet)
                    emails  = re.findall(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', snippet)
                    phone   = phones[0] if phones else ""
                    email   = emails[0] if emails and "indiamart" not in emails[0] else ""

                    # Build IndiaMART subdomain as website
                    subdomain_match = re.search(r'https?://([^.]+)\.indiamart\.com', link)
                    website = ("https://" + subdomain_match.group(1) + ".indiamart.com") if subdomain_match else link

                    pain = PAIN_POINTS.get(category, [
                        "only listed on IndiaMART — invisible on Google",
                        "no professional website",
                        "missing inbound leads from Google Search",
                    ])

                    lead = IndiaMartLead(
                        name=title[:80],
                        company=title[:80],
                        website=website,
                        phone=phone,
                        email=email,
                        city=TARGET_CITY,
                        category=category,
                        indiamart_url=link,
                        products=snippet[:150],
                        pain_points=pain[:3],
                    )
                    cat_leads.append(lead)
                    print("[Found] " + title[:50] + " | phone=" + (phone or "—") + " | email=" + (email or "—"))

                time.sleep(1)

            # ── Enrich top 15 leads with real contact details ─────────────────
            print("\n[Enriching] Visiting " + str(min(15, len(cat_leads))) + " IndiaMART profiles for real contacts...")
            for i, lead in enumerate(cat_leads[:15]):
                details = self.enricher.enrich(lead.indiamart_url)
                if details["phone"]:
                    lead.phone = details["phone"]
                    print("  ✅ Phone: " + details["phone"] + " for " + lead.company[:40])
                if details["email"]:
                    lead.email = details["email"]
                    print("  ✅ Email: " + details["email"] + " for " + lead.company[:40])
                if details["owner"]:
                    lead.name = details["owner"]
                    lead.job_title = "Owner / Proprietor"
                if details["city"]:
                    lead.city = details["city"]
                cat_leads[i] = lead
                time.sleep(2)  # polite delay

            all_leads.extend(cat_leads[:max_per_category])
            print("[" + category + "] Done: " + str(len(cat_leads)) + " leads | with phone: " +
                  str(sum(1 for l in cat_leads if l.phone)) + " | with email: " +
                  str(sum(1 for l in cat_leads if l.email)))

        print("\n=== Total leads: " + str(len(all_leads)) + " ===")

        # Save to DB
        if all_leads:
            try:
                from database import init_db, save_leads
                init_db()
                saved = save_leads([asdict(l) for l in all_leads])
                print("[DB] Saved " + str(saved) + " leads")
            except Exception as e:
                print("[DB] Error: " + str(e))

        return all_leads


if __name__ == "__main__":
    pipeline = IndiaMartLeadPipeline()
    leads = pipeline.run(max_per_category=25)
    print("\nTop 10 leads with contacts:")
    for l in leads[:10]:
        print(l.company[:40], "|", l.city, "|", l.phone, "|", l.email)
