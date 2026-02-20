import os
import re
import json
import time
import requests
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.indiamart.com/",
    "Connection": "keep-alive",
}

# Target categories with IndiaMART search URLs
CATEGORIES = {
    "Clothing & Textiles": [
        "https://www.indiamart.com/proddetail/clothing-manufacturers.html",
        "https://www.indiamart.com/search.mp?ss=clothing+manufacturer+india",
        "https://www.indiamart.com/search.mp?ss=textile+manufacturer+india",
        "https://www.indiamart.com/search.mp?ss=garment+manufacturer+india",
        "https://www.indiamart.com/search.mp?ss=fashion+clothing+supplier",
    ],
    "Electronics & Components": [
        "https://www.indiamart.com/search.mp?ss=electronics+manufacturer+india",
        "https://www.indiamart.com/search.mp?ss=electronic+components+supplier",
        "https://www.indiamart.com/search.mp?ss=led+lights+manufacturer+india",
        "https://www.indiamart.com/search.mp?ss=pcb+manufacturer+india",
    ],
    "Food & Beverages": [
        "https://www.indiamart.com/search.mp?ss=food+products+manufacturer+india",
        "https://www.indiamart.com/search.mp?ss=spices+manufacturer+india",
        "https://www.indiamart.com/search.mp?ss=snacks+manufacturer+india",
        "https://www.indiamart.com/search.mp?ss=beverages+manufacturer+india",
    ],
    "Furniture & Home Decor": [
        "https://www.indiamart.com/search.mp?ss=furniture+manufacturer+india",
        "https://www.indiamart.com/search.mp?ss=home+decor+manufacturer+india",
        "https://www.indiamart.com/search.mp?ss=wooden+furniture+manufacturer",
        "https://www.indiamart.com/search.mp?ss=modular+furniture+manufacturer",
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


class IndiaMartScraper:

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def scrape_search_page(self, url, category):
        """Scrape an IndiaMART search results page and extract seller listings."""
        leads = []
        try:
            print("[IndiaMART] Fetching: " + url)
            resp = self.session.get(url, timeout=20)

            if resp.status_code == 403:
                print("[IndiaMART] 403 blocked on: " + url)
                return []
            if resp.status_code != 200:
                print("[IndiaMART] Status " + str(resp.status_code) + " for: " + url)
                return []

            soup = BeautifulSoup(resp.text, "html.parser")

            # IndiaMART listing cards — multiple possible selectors
            cards = (
                soup.find_all("div", class_="card-wrap") or
                soup.find_all("div", class_=re.compile(r"listing|supplier|product-listing")) or
                soup.find_all("div", attrs={"data-id": True}) or
                soup.find_all("li", class_=re.compile(r"item|listing"))
            )

            print("[IndiaMART] Found " + str(len(cards)) + " cards on page")

            for card in cards:
                lead = self._parse_card(card, category, url)
                if lead:
                    leads.append(lead)

            # If no cards found, try extracting from JSON-LD or script tags
            if not leads:
                leads = self._extract_from_scripts(soup, category, url)

        except Exception as e:
            print("[IndiaMART] Exception: " + str(e))

        return leads

    def _parse_card(self, card, category, page_url):
        """Parse a single IndiaMART listing card."""
        try:
            # Company name
            company = ""
            for sel in ["h3", "h2", ".company-name", ".supplier-name", "[class*='comp']"]:
                el = card.select_one(sel)
                if el and el.get_text(strip=True):
                    company = el.get_text(strip=True)[:80]
                    break

            if not company or len(company) < 2:
                return None

            # Phone number
            phone = ""
            phone_el = card.select_one("[class*='phone'], [class*='mobile'], [href^='tel:']")
            if phone_el:
                raw = phone_el.get("href", "") or phone_el.get_text()
                phones = re.findall(r'[6-9]\d{9}', raw)
                if phones:
                    phone = phones[0]

            # Also search raw text for phone
            if not phone:
                raw_text = card.get_text()
                phones = re.findall(r'[6-9]\d{9}', raw_text)
                if phones:
                    phone = phones[0]

            # City / Location
            city = "India"
            for sel in ["[class*='locat'], [class*='city'], [class*='address']"]:
                el = card.select_one(sel)
                if el:
                    city = el.get_text(strip=True)[:40]
                    break

            # IndiaMART profile URL
            indiamart_url = ""
            link = card.find("a", href=re.compile(r"indiamart\.com"))
            if link:
                indiamart_url = link.get("href", "")

            # Products
            products = ""
            prod_el = card.select_one("[class*='product'], [class*='item-name']")
            if prod_el:
                products = prod_el.get_text(strip=True)[:100]

            # Build IndiaMART subdomain website
            # Format: companyname.indiamart.com
            website = ""
            if indiamart_url:
                match = re.search(r'https?://([^.]+)\.indiamart\.com', indiamart_url)
                if match:
                    website = "https://" + match.group(1) + ".indiamart.com"

            pain = self._get_pain_points(category, website)

            return IndiaMartLead(
                name=company,
                company=company,
                website=website or indiamart_url,
                phone=phone,
                email="",
                city=city,
                category=category,
                indiamart_url=indiamart_url,
                products=products,
                pain_points=pain,
            )

        except Exception as e:
            return None

    def _extract_from_scripts(self, soup, category, page_url):
        """Extract structured data from JSON-LD or inline scripts."""
        leads = []
        try:
            scripts = soup.find_all("script", type="application/ld+json")
            for script in scripts:
                try:
                    data = json.loads(script.string or "{}")
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        name = item.get("name", "")
                        phone = item.get("telephone", "")
                        city = (item.get("address") or {}).get("addressLocality", "India")
                        url = item.get("url", "")
                        if name and len(name) > 2:
                            leads.append(IndiaMartLead(
                                name=name, company=name,
                                website=url, phone=phone,
                                email="", city=city,
                                category=category,
                                indiamart_url=page_url,
                                pain_points=self._get_pain_points(category, url),
                            ))
                except Exception:
                    continue
        except Exception as e:
            print("[IndiaMART] Script extract error: " + str(e))
        return leads

    def _get_pain_points(self, category, website):
        """Generate relevant pain points based on category."""
        base = [
            "only has IndiaMART microsite — no real website",
            "invisible on Google Search — losing customers daily",
            "no SEO presence — competitors ranking above them",
        ]
        category_specific = {
            "Clothing & Textiles":       "missing B2B + B2C online store — leaving money on table",
            "Electronics & Components":  "no product catalog website — buyers can't find specs online",
            "Food & Beverages":          "no direct-to-consumer website — fully dependent on intermediaries",
            "Furniture & Home Decor":    "no portfolio website — losing premium customers to competitors",
        }
        specific = category_specific.get(category, "no professional website")
        return [specific] + base[:2]

    def scrape_seller_profile(self, indiamart_url):
        """Scrape individual seller profile page for email + more details."""
        result = {"email": "", "phone": "", "name": ""}
        if not indiamart_url:
            return result
        try:
            resp = self.session.get(indiamart_url, timeout=15)
            if resp.status_code != 200:
                return result
            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text()

            # Email
            emails = re.findall(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', text)
            skip = ["indiamart", "example", "noreply", "support@"]
            for e in emails:
                if not any(s in e for s in skip):
                    result["email"] = e
                    break

            # Phone
            phones = re.findall(r'[6-9]\d{9}', text)
            if phones:
                result["phone"] = phones[0]

            # Owner name
            for pattern in [r'Mr\.\s+([A-Z][a-z]+ [A-Z][a-z]+)', r'Ms\.\s+([A-Z][a-z]+ [A-Z][a-z]+)', r'Owner[:\s]+([A-Z][a-z]+ [A-Z][a-z]+)']:
                match = re.search(pattern, resp.text)
                if match:
                    result["name"] = match.group(1)
                    break

        except Exception as e:
            print("[IndiaMART] Profile error: " + str(e))
        return result


class IndiaMartLeadPipeline:

    def __init__(self):
        self.scraper = IndiaMartScraper()

    def run(self, max_per_category=25):
        all_leads = []
        seen = set()

        for category, urls in CATEGORIES.items():
            print("\n=== Category: " + category + " ===")
            cat_leads = []

            for url in urls:
                if len(cat_leads) >= max_per_category:
                    break

                page_leads = self.scraper.scrape_search_page(url, category)

                for lead in page_leads:
                    key = lead.company.lower().strip()
                    if key and key not in seen:
                        seen.add(key)
                        cat_leads.append(lead)

                print("[IndiaMART] " + category + ": " + str(len(cat_leads)) + " leads so far")
                time.sleep(3)  # polite delay

            # Enrich top leads with profile scraping (email + owner name)
            print("[IndiaMART] Enriching " + str(min(10, len(cat_leads))) + " profiles for " + category)
            for i, lead in enumerate(cat_leads[:10]):
                if lead.indiamart_url and not lead.email:
                    details = self.scraper.scrape_seller_profile(lead.indiamart_url)
                    if details["email"]:
                        lead.email = details["email"]
                    if details["phone"] and not lead.phone:
                        lead.phone = details["phone"]
                    if details["name"]:
                        lead.name = details["name"]
                    cat_leads[i] = lead
                time.sleep(1)

            all_leads.extend(cat_leads[:max_per_category])
            print("[IndiaMART] " + category + " done: " + str(len(cat_leads)) + " leads")

        print("\n=== Total IndiaMART Leads: " + str(len(all_leads)) + " ===")

        # Save to DB
        try:
            from database import init_db, save_leads
            init_db()
            saved = save_leads([asdict(l) for l in all_leads])
            print("[DB] Saved " + str(saved) + " IndiaMART leads")
        except Exception as e:
            print("[DB] Error: " + str(e))
            with open("indiamart_leads.json", "w") as f:
                json.dump([asdict(l) for l in all_leads], f, indent=2)
            print("[Fallback] Saved to indiamart_leads.json")

        return all_leads


if __name__ == "__main__":
    pipeline = IndiaMartLeadPipeline()
    leads = pipeline.run(max_per_category=25)
    print("\nTop 10 leads:")
    for l in leads[:10]:
        print(l.company, "|", l.city, "|", l.phone, "|", l.email, "|", l.website)
