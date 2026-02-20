import os
import re
import json
import time
import requests
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")

CATEGORIES = {
    "Chemicals": [
        "chemical manufacturer kanpur",
        "chemical supplier kanpur india",
        "industrial chemical kanpur",
        "agrochemical manufacturer kanpur",
        "paint chemical manufacturer kanpur",
        "cleaning chemical supplier kanpur",
        "pharmaceutical chemical kanpur",
        "fertilizer manufacturer kanpur",
    ],
}
TARGET_CITY = "Kanpur"

PAIN_POINTS = {
    "Chemicals": [
        "only listed on IndiaMART — invisible on Google Search",
        "buyers cannot find product specs or MSDS sheets online",
        "no professional website — losing B2B buyers to competitors",
        "no online inquiry form — missing inbound leads daily",
        "competitors with real websites rank above them on Google",
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
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html",
        "Accept-Language": "en-IN,en;q=0.9",
    }

    def enrich(self, indiamart_url):
        result = {"phone": "", "email": "", "owner": "", "real_website": ""}
        if not indiamart_url or "indiamart.com" not in indiamart_url:
            return result
        try:
            resp = requests.get(indiamart_url, headers=self.HEADERS, timeout=12)
            if resp.status_code != 200:
                return result
            html = resp.text
            text = re.sub(r'<[^>]+>', ' ', html)

            # ── Real phone ────────────────────────────────────────────────────
            phones = re.findall(r'(?:\+91[\s-]?|0)?[6-9]\d{9}', text)
            skip   = ["9696969696", "8888888888", "9999999999"]
            for p in phones:
                digits = re.sub(r'\D', '', p)[-10:]
                if len(digits) == 10 and digits not in skip:
                    result["phone"] = digits
                    break

            # ── Real email ────────────────────────────────────────────────────
            emails = re.findall(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', text)
            skip_e = ["indiamart", "example", "noreply", "support", "care@", "help@"]
            for e in emails:
                if not any(s in e.lower() for s in skip_e) and len(e) < 60:
                    result["email"] = e
                    break

            # ── Owner name ────────────────────────────────────────────────────
            for pattern in [
                r'Contact\s+Person[:\s]+([A-Z][a-zA-Z\s]{2,25})',
                r'Mr\.\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
                r'Ms\.\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
                r'Proprietor[:\s]+([A-Z][a-zA-Z\s]{2,25})',
            ]:
                m = re.search(pattern, html)
                if m:
                    result["owner"] = m.group(1).strip()[:50]
                    break

            # ── Real website (not indiamart subdomain) ────────────────────────
            # Look for external links in the page that are the seller's real domain
            ext_links = re.findall(r'href=["\']?(https?://(?!(?:www\.)?indiamart)[^\s"\'<>]+)["\']?', html)
            skip_domains = ["facebook.com", "twitter.com", "linkedin.com", "youtube.com",
                           "google.com", "instagram.com", "indiamart.com", "javascript"]
            for link in ext_links:
                domain = re.sub(r'https?://(www\.)?', '', link).split('/')[0]
                if domain and not any(s in domain for s in skip_domains) and '.' in domain:
                    result["real_website"] = "https://" + domain
                    break

        except Exception as e:
            print("[Enricher] Error: " + str(e)[:80])
        return result


class RealWebsiteFinder:
    """
    If seller has no real website on their IndiaMART page,
    search Google for their company name to find it.
    """
    def find(self, company_name, city):
        if not SERPAPI_KEY:
            return ""
        try:
            resp = requests.get("https://serpapi.com/search", params={
                "q":       company_name + " " + city + " official website",
                "api_key": SERPAPI_KEY,
                "num":     3,
                "gl":      "in",
            }, timeout=10)
            if resp.status_code != 200:
                return ""
            results = resp.json().get("organic_results", [])
            skip = ["indiamart", "justdial", "tradeindia", "exportersindia",
                   "facebook", "linkedin", "instagram", "quora", "wikipedia"]
            for r in results:
                link = r.get("link", "")
                if not any(s in link for s in skip):
                    return link
        except Exception:
            pass
        return ""


class SerpAPISource:
    BASE_URL = "https://serpapi.com/search"

    def search(self, query, num=10):
        if not SERPAPI_KEY:
            print("[SerpAPI] No SERPAPI_KEY")
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
            print("[SerpAPI] '" + query + "' -> " + str(len(results)) + " results")
            return results
        except Exception as e:
            print("[SerpAPI] Exception: " + str(e))
            return []


class IndiaMartLeadPipeline:

    def __init__(self):
        self.serp    = SerpAPISource()
        self.enrich  = ContactEnricher()
        self.finder  = RealWebsiteFinder()

    def clear_old_leads(self):
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

    def run(self, max_per_category=25, clear_first=False):
        if clear_first:
            print("=== Clearing old leads ===")
            self.clear_old_leads()

        # Load existing company names from DB to avoid duplicates
        existing_names = set()
        try:
            from database import load_leads
            existing = load_leads(limit=1000)
            for e in existing:
                name = (e.get("company") or e.get("name") or "").lower().strip()
                if name:
                    existing_names.add(name)
            print("[Dedup] Found " + str(len(existing_names)) + " existing leads in DB — will skip duplicates")
        except Exception as e:
            print("[Dedup] Could not load existing: " + str(e))

        all_leads = []
        seen      = set(existing_names)

        for category, queries in CATEGORIES.items():
            print("\n=== " + category + " | " + TARGET_CITY + " ===")
            cat_leads = []

            for query in queries:
                if len(cat_leads) >= max_per_category:
                    break
                results = self.serp.search(query, num=10)
                for r in results:
                    title   = r.get("title", "").strip()[:80]
                    link    = r.get("link", "")
                    snippet = r.get("snippet", "")
                    if not link or "indiamart.com" not in link:
                        continue
                    if title in seen:
                        continue
                    seen.add(title)

                    phones = re.findall(r'[6-9]\d{9}', snippet)
                    emails = re.findall(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', snippet)
                    phone  = phones[0] if phones else ""
                    email  = emails[0] if emails and "indiamart" not in (emails[0] if emails else "") else ""

                    pain = PAIN_POINTS.get(category, [
                        "only on IndiaMART — invisible on Google",
                        "no professional website",
                        "missing inbound leads from Google Search",
                    ])

                    cat_leads.append(IndiaMartLead(
                        name=title, company=title,
                        website="",  # will be filled by enricher
                        phone=phone, email=email,
                        city=TARGET_CITY, category=category,
                        indiamart_url=link,
                        products=snippet[:150],
                        pain_points=pain[:3],
                    ))
                    print("[Found] " + title[:50])
                time.sleep(1)

            # ── Enrich with real contacts + real website ───────────────────────
            print("\n[Enriching] " + str(len(cat_leads)) + " leads...")
            for i, lead in enumerate(cat_leads):
                details = self.enrich.enrich(lead.indiamart_url)

                if details["phone"]:
                    lead.phone = details["phone"]
                    print("  Phone: " + details["phone"] + " | " + lead.company[:40])
                if details["email"]:
                    lead.email = details["email"]
                    print("  Email: " + details["email"])
                if details["owner"]:
                    lead.name     = details["owner"]
                    lead.job_title = "Owner / Proprietor"
                if details["real_website"]:
                    lead.website = details["real_website"]
                    print("  Website: " + details["real_website"])
                elif not lead.website:
                    # Last resort — Google their company name
                    real = self.finder.find(lead.company, TARGET_CITY)
                    if real:
                        lead.website = real
                        print("  Website (Google): " + real)
                    else:
                        # Fallback: WhatsApp link if phone found
                        if lead.phone:
                            lead.website = "https://wa.me/91" + lead.phone
                            print("  WhatsApp: wa.me/91" + lead.phone)
                        else:
                            lead.website = lead.indiamart_url

                cat_leads[i] = lead
                time.sleep(2)

            all_leads.extend(cat_leads[:max_per_category])
            has_phone   = sum(1 for l in cat_leads if l.phone)
            has_email   = sum(1 for l in cat_leads if l.email)
            has_website = sum(1 for l in cat_leads if l.website and "indiamart" not in l.website)
            print("\n[" + category + "] " + str(len(cat_leads)) + " leads | " +
                  str(has_phone) + " phones | " +
                  str(has_email) + " emails | " +
                  str(has_website) + " real websites")

        print("\n=== Total: " + str(len(all_leads)) + " leads ===")

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
    print("\nTop 10:")
    for l in leads[:10]:
        print(l.company[:35], "|", l.phone, "|", l.email, "|", l.website[:40])
