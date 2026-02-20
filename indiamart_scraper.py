import os
import re
import json
import time
import requests
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional

# IndiaMART Official Lead Manager API
# Sign up FREE at: https://seller.indiamart.com/lms/
# Go to: My IndiaMART → Lead Manager → API Access
# You get: INDIAMART_API_KEY and INDIAMART_MOBILE (your registered mobile)
INDIAMART_API_KEY = os.getenv("INDIAMART_API_KEY", "")
INDIAMART_MOBILE  = os.getenv("INDIAMART_MOBILE", "")

# SerpAPI — real Google results including IndiaMART pages
# Free: 100 searches/month at serpapi.com
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")


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


# ── Source 1: IndiaMART Official Lead Manager API ─────────────────────────────
class IndiaMartAPISource:
    """
    Uses IndiaMART's official Lead Manager API.
    FREE for all IndiaMART sellers.
    Setup: https://seller.indiamart.com → Lead Manager → API
    Returns: your own incoming buyer leads from IndiaMART
    """
    BASE_URL = "https://mapi.indiamart.com/wservce/crm/crmListing/v2/"

    def get_leads(self, start_time=None, end_time=None):
        if not INDIAMART_API_KEY or not INDIAMART_MOBILE:
            print("[IndiaMartAPI] No credentials — set INDIAMART_API_KEY and INDIAMART_MOBILE")
            return []

        params = {
            "glusr_trans_id": INDIAMART_API_KEY,
            "mobile":         INDIAMART_MOBILE,
            "start_time":     start_time or "01-Jan-2024 00:00:00",
            "end_time":       end_time or datetime.utcnow().strftime("%d-%b-%Y %H:%M:%S"),
        }
        try:
            resp = requests.get(self.BASE_URL, params=params, timeout=15)
            print("[IndiaMartAPI] Status: " + str(resp.status_code))
            if resp.status_code != 200:
                print("[IndiaMartAPI] Error: " + resp.text[:200])
                return []

            data  = resp.json()
            items = data.get("RESPONSE", data.get("response", []))
            leads = []
            for item in items:
                company = item.get("SENDER_COMPANY", "") or item.get("sender_company", "")
                name    = item.get("SENDER_NAME", "") or item.get("sender_name", company)
                phone   = item.get("SENDER_MOBILE", "") or item.get("sender_mobile", "")
                email   = item.get("SENDER_EMAIL", "") or item.get("sender_email", "")
                city    = item.get("SENDER_CITY", "") or item.get("sender_city", "India")
                product = item.get("QUERY_PRODUCT_NAME", "") or ""

                leads.append(IndiaMartLead(
                    name=name, company=company,
                    website="", phone=phone, email=email,
                    city=city, products=product,
                    pain_points=[
                        "only has IndiaMART microsite — no real website",
                        "invisible on Google Search",
                        "losing customers to competitors with real websites",
                    ]
                ))
                print("[IndiaMartAPI] Lead: " + name + " | " + company + " | " + city)

            print("[IndiaMartAPI] Got " + str(len(leads)) + " leads")
            return leads

        except Exception as e:
            print("[IndiaMartAPI] Exception: " + str(e))
            return []


# ── Source 2: SerpAPI — search Google for IndiaMART seller pages ──────────────
class SerpAPISource:
    """
    Uses SerpAPI to search Google for IndiaMART seller profiles.
    Free: 100 searches/month
    Sign up: https://serpapi.com
    Add to Railway: SERPAPI_KEY=your_key
    """
    BASE_URL = "https://serpapi.com/search"

    QUERIES = [
        "site:indiamart.com clothing manufacturer contact",
        "site:indiamart.com textile supplier india email",
        "site:indiamart.com electronics manufacturer contact",
        "site:indiamart.com led manufacturer india",
        "site:indiamart.com food products manufacturer contact",
        "site:indiamart.com spices supplier india email",
        "site:indiamart.com furniture manufacturer contact",
        "site:indiamart.com home decor supplier india",
        "site:indiamart.com garment exporter contact email",
        "site:indiamart.com handicraft manufacturer india",
    ]

    CATEGORY_MAP = {
        "clothing": "Clothing & Textiles",
        "textile":  "Clothing & Textiles",
        "garment":  "Clothing & Textiles",
        "electronics": "Electronics & Components",
        "led":      "Electronics & Components",
        "food":     "Food & Beverages",
        "spices":   "Food & Beverages",
        "furniture":"Furniture & Home Decor",
        "decor":    "Furniture & Home Decor",
        "handicraft":"Furniture & Home Decor",
    }

    def __init__(self):
        self.key = SERPAPI_KEY

    def search(self, max_leads=100):
        if not self.key:
            print("[SerpAPI] No SERPAPI_KEY set — skipping")
            return []

        all_leads = []
        seen = set()

        for query in self.QUERIES:
            if len(all_leads) >= max_leads:
                break
            try:
                resp = requests.get(self.BASE_URL, params={
                    "q":       query,
                    "api_key": self.key,
                    "num":     10,
                    "hl":      "en",
                    "gl":      "in",
                }, timeout=15)

                if resp.status_code != 200:
                    print("[SerpAPI] Error " + str(resp.status_code))
                    continue

                results = resp.json().get("organic_results", [])
                print("[SerpAPI] Query: " + query[:50] + " → " + str(len(results)) + " results")

                # Determine category from query
                cat = "General"
                for kw, c in self.CATEGORY_MAP.items():
                    if kw in query:
                        cat = c
                        break

                for r in results:
                    title   = r.get("title", "")
                    snippet = r.get("snippet", "")
                    link    = r.get("link", "")

                    if "indiamart.com" not in link:
                        continue
                    if title in seen:
                        continue
                    seen.add(title)

                    # Extract phone from snippet
                    phones = re.findall(r'[6-9]\d{9}', snippet)
                    phone  = phones[0] if phones else ""

                    # Extract email from snippet
                    emails = re.findall(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', snippet)
                    email  = emails[0] if emails else ""

                    # Extract city
                    city = "India"
                    indian_cities = ["Mumbai","Delhi","Bangalore","Hyderabad","Chennai",
                                    "Kolkata","Pune","Ahmedabad","Surat","Jaipur",
                                    "Lucknow","Noida","Gurugram","Indore","Bhopal"]
                    for c in indian_cities:
                        if c.lower() in snippet.lower():
                            city = c
                            break

                    # Build IndiaMART subdomain website
                    website = ""
                    match = re.search(r'https?://([^.]+)\.indiamart\.com', link)
                    if match:
                        website = "https://" + match.group(1) + ".indiamart.com"

                    all_leads.append(IndiaMartLead(
                        name=title[:60],
                        company=title[:60],
                        website=website or link,
                        phone=phone,
                        email=email,
                        city=city,
                        category=cat,
                        indiamart_url=link,
                        products=snippet[:100],
                        pain_points=[
                            "only has IndiaMART microsite — no real website",
                            "invisible on Google Search — losing customers daily",
                            "no SEO presence — competitors ranking above them",
                        ]
                    ))
                    print("[SerpAPI] Found: " + title[:50] + " | " + city)

                time.sleep(1)

            except Exception as e:
                print("[SerpAPI] Exception: " + str(e))

        print("[SerpAPI] Total: " + str(len(all_leads)) + " leads")
        return all_leads


# ── Main Pipeline ─────────────────────────────────────────────────────────────
class IndiaMartLeadPipeline:

    def __init__(self):
        self.api_source  = IndiaMartAPISource()
        self.serp_source = SerpAPISource()

    def run(self, max_per_category=25):
        all_leads = []
        seen = set()

        def add(leads):
            for l in leads:
                key = (l.company or l.name).lower().strip()
                if key and key not in seen:
                    seen.add(key)
                    all_leads.append(l)

        # Source 1: IndiaMART Official API (if credentials set)
        print("\n=== Source 1: IndiaMART Lead Manager API ===")
        add(self.api_source.get_leads())

        # Source 2: SerpAPI Google Search (if key set)
        print("\n=== Source 2: SerpAPI Google Search ===")
        add(self.serp_source.search(max_leads=max_per_category * 4))

        print("\n=== Total: " + str(len(all_leads)) + " IndiaMART leads ===")

        if not all_leads:
            print("[Pipeline] 0 leads found.")
            print("[Pipeline] To get leads, set one of:")
            print("  INDIAMART_API_KEY + INDIAMART_MOBILE (free from seller.indiamart.com)")
            print("  SERPAPI_KEY (free 100/mo from serpapi.com)")
            return []

        # Save to DB
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
    print("\nTop 10:")
    for l in leads[:10]:
        print(l.company, "|", l.city, "|", l.phone, "|", l.website)
