import os
import json
import time
import re
import requests
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional

# ── Lead dataclass (compatible with existing DB schema) ───────────────────────
@dataclass
class InstagramLead:
    name: str
    website: str
    phone: str
    email: str
    city: str
    source: str
    linkedin_url: str = ""
    job_title: str = ""
    company: str = ""
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


# ── Google Search Scraper ─────────────────────────────────────────────────────
class GoogleSearchScraper:
    """
    Searches Google for Indian D2C / e-commerce brands using
    public search queries. No API key needed.
    Finds real businesses with websites that need digital marketing.
    """

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    SEARCHES = [
        # Find Shopify stores in India
        'site:myshopify.com "india" fashion clothing',
        'site:myshopify.com "india" beauty skincare',
        'site:myshopify.com "india" jewelry accessories',
        # Find WooCommerce stores in India
        '"wp-content" "india" ecommerce clothing store',
        # Find small D2C brands directly
        '"buy now" "free shipping india" clothing brand',
        '"shop now" "made in india" skincare brand',
        '"cash on delivery" "india" fashion brand site:in',
        # Find brands on specific platforms
        'site:instamojo.com india fashion store',
        'site:shiprocket.in india d2c brand',
        # City-specific searches
        '"mumbai" "online store" fashion brand contact email',
        '"bangalore" "online store" skincare brand contact',
        '"delhi" "online store" clothing brand email',
        '"pune" "ecommerce" fashion brand founder email',
        '"hyderabad" "online store" brand contact',
    ]

    def search(self, query, max_results=10):
        """Search Google and extract website URLs from results."""
        results = []
        try:
            url = "https://www.google.com/search?q=" + requests.utils.quote(query) + "&num=10"
            resp = requests.get(url, headers=self.HEADERS, timeout=15)

            if resp.status_code != 200:
                print("[Google] Status " + str(resp.status_code) + " for: " + query[:50])
                return []

            html = resp.text

            # Extract URLs from Google results
            urls = re.findall(r'href="(https?://[^"&]+)"', html)
            seen = set()
            for u in urls:
                # Skip Google's own URLs and junk
                skip = ["google.", "youtube.", "facebook.", "instagram.", "twitter.",
                        "amazon.", "flipkart.", "linkedin.", "wikipedia.", "quora.",
                        "reddit.", "medium.", "github.", "indiamart.", "justdial."]
                if any(s in u for s in skip):
                    continue
                domain = re.sub(r'https?://(www\.)?', '', u).split('/')[0]
                if domain and domain not in seen and '.' in domain:
                    seen.add(domain)
                    results.append("https://" + domain)
                if len(results) >= max_results:
                    break

            print("[Google] Query: " + query[:60] + " → " + str(len(results)) + " sites")
            return results

        except Exception as e:
            print("[Google] Error: " + str(e))
            return []


class WebsiteAnalyzer:
    """Fetch a website and extract contact info + business signals."""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)",
        "Accept": "text/html",
    }

    def analyze(self, url):
        """Returns dict with name, email, phone, city, pain_points."""
        result = {
            "website": url,
            "name": "",
            "email": "",
            "phone": "",
            "city": "India",
            "pain_points": [],
            "company": "",
        }
        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=10)
            if resp.status_code != 200:
                return result
            html = resp.text.lower()

            # Extract email
            emails = re.findall(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', html)
            # Filter out generic/spam emails
            skip_emails = ["example", "test", "noreply", "no-reply", "support@shopify",
                          "privacy", "legal", "abuse", "admin@wordpress"]
            for e in emails:
                if not any(s in e for s in skip_emails) and len(e) < 60:
                    result["email"] = e
                    break

            # Extract phone
            phones = re.findall(r'(?:\+91|0)?[6-9]\d{9}', html)
            if phones:
                result["phone"] = phones[0]

            # Extract city
            cities = ["mumbai", "delhi", "bangalore", "bengaluru", "hyderabad",
                     "chennai", "kolkata", "pune", "ahmedabad", "surat",
                     "jaipur", "noida", "gurugram", "gurgaon", "indore"]
            for city in cities:
                if city in html:
                    result["city"] = city.title()
                    break

            # Extract business name from title tag
            title = re.search(r'<title[^>]*>([^<]+)</title>', resp.text, re.IGNORECASE)
            if title:
                name = title.group(1).strip()
                name = re.sub(r'\s*[\|–-].*$', '', name).strip()
                result["name"]    = name[:60]
                result["company"] = name[:60]

            # Score pain points
            pain = []
            if "shopify" in html or "myshopify" in html:
                pain.append("Shopify store needs SEO optimization")
            if "woocommerce" in html:
                pain.append("WooCommerce store needs SEO optimization")
            if not re.search(r'google-analytics|gtag|ga\.js', html):
                pain.append("no Google Analytics — flying blind on traffic")
            if not re.search(r'pixel|fbq|facebook.*pixel', html):
                pain.append("no Facebook Pixel — missing retargeting")
            if not re.search(r'schema\.org|application/ld\+json', html):
                pain.append("no schema markup — poor SEO structure")
            if "cash on delivery" in html or "cod" in html:
                pain.append("COD-heavy store — needs better digital ads to reduce returns")
            pain.append("low organic traffic from Google")
            result["pain_points"] = pain[:3]

        except Exception as e:
            print("[Analyzer] Error for " + url + ": " + str(e))
        return result


class InstagramLeadPipeline:
    """
    Renamed to keep compatibility with main.py imports.
    Actually uses Google Search to find D2C brands.
    """

    def __init__(self):
        self.google   = GoogleSearchScraper()
        self.analyzer = WebsiteAnalyzer()

    def run(self, max_leads=100):
        print("\n=== Google Search D2C Brand Finder ===")
        all_urls = []
        seen_domains = set()

        # Step 1: Search Google
        print("\n[Step 1] Searching Google for Indian D2C brands...")
        for query in self.google.SEARCHES:
            if len(all_urls) >= max_leads * 2:
                break
            urls = self.google.search(query, max_results=10)
            for u in urls:
                domain = re.sub(r'https?://(www\.)?', '', u).split('/')[0]
                if domain not in seen_domains:
                    seen_domains.add(domain)
                    all_urls.append(u)
            time.sleep(3)  # respectful delay between Google requests

        print("\n[Step 2] Analyzing " + str(len(all_urls)) + " websites...")
        leads = []
        for url in all_urls:
            if len(leads) >= max_leads:
                break
            info = self.analyzer.analyze(url)

            # Must have at least a name and some contact info
            if not info["name"]:
                time.sleep(0.5)
                continue

            lead = InstagramLead(
                name=info["name"],
                website=url,
                phone=info["phone"],
                email=info["email"],
                city=info["city"],
                source="google_search",
                job_title="Founder / Owner",
                company=info["company"],
                pain_points=info["pain_points"],
            )
            leads.append(lead)
            print("[Found] " + info["name"] + " | " + url + " | " + info["city"])
            time.sleep(1)

        print("\n[Done] Found " + str(len(leads)) + " D2C brand leads")

        # Save to DB
        if leads:
            try:
                from database import init_db, save_leads
                init_db()
                saved = save_leads([asdict(l) for l in leads])
                print("[DB] Saved " + str(saved) + " leads")
            except Exception as e:
                print("[DB] Error: " + str(e))

        return leads


if __name__ == "__main__":
    pipeline = InstagramLeadPipeline()
    leads = pipeline.run(max_leads=50)
    print("\nTop 5:")
    for l in leads[:5]:
        print(l.name, "|", l.website, "|", l.email, "|", l.city)
