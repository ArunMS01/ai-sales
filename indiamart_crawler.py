"""
INDIAMART REAL CRAWLER
=======================
Uses ScrapingBee to bypass IndiaMART's bot protection.
Extracts: products, description, year, certifications, 
          turnover, employees, GST, contact info.

Get free API key: https://www.scrapingbee.com (1000 free credits)
Set env var: SCRAPINGBEE_KEY=your_key_here
"""
import os, re, json, time, requests
from bs4 import BeautifulSoup

SCRAPINGBEE_KEY = os.getenv("SCRAPINGBEE_KEY", "")
OPENAI_KEY      = os.getenv("OPENAI_API_KEY", "")

# ─────────────────────────────────────────────────────────────────────────────
# SCRAPINGBEE FETCHER — renders JS, rotates IPs, bypasses captcha
# ─────────────────────────────────────────────────────────────────────────────
class ScrapingBeeFetcher:

    API_URL = "https://app.scrapingbee.com/api/v1/"

    def fetch(self, url):
        """Fetch any IndiaMART page with full JS rendering."""
        if not SCRAPINGBEE_KEY:
            print("[Crawler] No SCRAPINGBEE_KEY set")
            return None

        try:
            r = requests.get(self.API_URL, params={
                "api_key":         SCRAPINGBEE_KEY,
                "url":             url,
                "render_js":       "true",      # renders JavaScript
                "premium_proxy":   "true",      # Indian IP, harder to block
                "block_ads":       "true",
                "block_resources": "false",
                "wait":            2000,         # wait 2s for JS to load
                "country_code":    "in",         # Indian proxy
            }, timeout=30)

            if r.status_code == 200:
                print(f"[Crawler] ✅ Fetched {url[:60]} ({len(r.text)} chars)")
                return r.text
            else:
                print(f"[Crawler] ❌ Status {r.status_code} for {url[:60]}")
                print(f"[Crawler] Response: {r.text[:200]}")
                return None

        except Exception as e:
            print(f"[Crawler] Error: {e}")
            return None


# ─────────────────────────────────────────────────────────────────────────────
# INDIAMART PARSER — extracts every field from seller page HTML
# ─────────────────────────────────────────────────────────────────────────────
class IndiaMArtParser:

    def parse(self, html, company_name=""):
        """Parse IndiaMART seller profile HTML into structured data."""
        if not html:
            return {}

        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        data = {
            "products":      [],
            "description":   "",
            "year":          "",
            "gst":           "",
            "turnover":      "",
            "employees":     "",
            "certifications":[],
            "phone":         "",
            "email":         "",
            "address":       "",
            "nature":        "",  # manufacturer / trader / exporter
        }

        # ── Products ─────────────────────────────────────────────────────────
        # IndiaMART product cards have multiple possible class names
        product_selectors = [
            {"class": re.compile(r"product|prd|item|catalog|prod", re.I)},
        ]
        seen = set()
        for sel in product_selectors:
            for el in soup.find_all(["div","li","a","h3","h4"], attrs=sel):
                name = el.get_text(strip=True)
                # Clean up — remove prices, codes, garbage
                name = re.sub(r'₹[\d,]+.*', '', name).strip()
                name = re.sub(r'Get Latest Price', '', name, flags=re.I).strip()
                name = re.sub(r'View More.*', '', name, flags=re.I).strip()
                if name and 3 < len(name) < 80 and name not in seen:
                    seen.add(name)
                    data["products"].append(name)
                if len(data["products"]) >= 12:
                    break

        # Also try meta tags — IndiaMART puts product names in keywords
        meta_kw = soup.find("meta", {"name": "keywords"})
        if meta_kw and len(data["products"]) < 3:
            kws = [k.strip() for k in meta_kw.get("content","").split(",")]
            for kw in kws:
                if kw and kw not in seen and 3 < len(kw) < 60:
                    data["products"].append(kw)
                    seen.add(kw)

        # Try title tag — often "Product1, Product2 Manufacturer - Company"
        title = soup.find("title")
        if title and len(data["products"]) < 3:
            title_text = title.get_text()
            # Extract before "Manufacturer" or "Supplier"
            match = re.match(r'^(.+?)\s+(?:Manufacturer|Supplier|Exporter)', title_text, re.I)
            if match:
                parts = [p.strip() for p in match.group(1).split(",")]
                for p in parts:
                    if p and p not in seen and len(p) > 3:
                        data["products"].append(p)
                        seen.add(p)

        # ── Description ──────────────────────────────────────────────────────
        desc_candidates = [
            soup.find(class_=re.compile(r"about|desc|overview|profile|intro|company-info", re.I)),
            soup.find("meta", {"name": "description"}),
            soup.find("p", class_=re.compile(r"about|desc", re.I)),
        ]
        for cand in desc_candidates:
            if cand:
                desc = cand.get("content") or cand.get_text(" ", strip=True)
                if desc and len(desc) > 50:
                    data["description"] = desc[:500]
                    break

        # ── Year Established ─────────────────────────────────────────────────
        year_patterns = [
            r'(?:established|est\.?|since|founded|incorporated)[^\d]*(\d{4})',
            r'(\d{4})\s*(?:established|founded)',
            r'in\s+(\d{4})',
        ]
        for pat in year_patterns:
            m = re.search(pat, text, re.I)
            if m and 1950 <= int(m.group(1)) <= 2024:
                data["year"] = m.group(1)
                break

        # ── GST Number ───────────────────────────────────────────────────────
        gst = re.search(r'\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}', text)
        if gst:
            data["gst"] = gst.group()

        # ── Annual Turnover ──────────────────────────────────────────────────
        turnover = re.search(
            r'(?:turnover|annual\s+turnover)[^\d₹]*([₹\d\.,]+\s*(?:crore|lakh|cr|lac|million|billion)?)',
            text, re.I
        )
        if turnover:
            data["turnover"] = turnover.group(1).strip()

        # ── Employees ────────────────────────────────────────────────────────
        emp = re.search(
            r'(\d+[\d\-\+]*)\s*(?:employees?|staff|workers?|people)',
            text, re.I
        )
        if emp:
            data["employees"] = emp.group(1)

        # ── Nature of business ───────────────────────────────────────────────
        for nature in ["Manufacturer","Exporter","Trader","Wholesaler","Retailer","Service Provider"]:
            if nature.lower() in text.lower():
                data["nature"] = nature
                break

        # ── Certifications ───────────────────────────────────────────────────
        cert_keywords = ["ISO","CE","BIS","GMP","HACCP","FSSAI","FDA","WHO","REACH","RoHS","MSME"]
        for cert in cert_keywords:
            if cert in text:
                data["certifications"].append(cert)

        # ── Contact ──────────────────────────────────────────────────────────
        phones = re.findall(r'[6-9]\d{9}', text)
        skip   = ["9696969696","8888888888","9999999999"]
        for p in phones:
            if p not in skip:
                data["phone"] = p
                break

        emails = re.findall(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', text)
        for e in emails:
            if "indiamart" not in e and len(e) < 60:
                data["email"] = e
                break

        # ── Address ──────────────────────────────────────────────────────────
        addr = re.search(
            r'(?:address|location|registered at)[:\s]*([A-Za-z0-9\s,\-\.]+(?:India)?)',
            text, re.I
        )
        if addr:
            data["address"] = addr.group(1).strip()[:150]

        print(f"[Parser] Products: {len(data['products'])} | Year: {data['year']} | GST: {data['gst']}")
        return data


# ─────────────────────────────────────────────────────────────────────────────
# OPENAI ENRICHER — fills gaps and writes unique content
# ─────────────────────────────────────────────────────────────────────────────
class OpenAIEnricher:

    def enrich(self, company, city, category, parsed_data):
        """Use OpenAI to fill gaps and generate unique copy from real data."""
        if not OPENAI_KEY:
            return parsed_data

        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_KEY)

            products_str = ", ".join(parsed_data.get("products", [])[:8]) or "unknown"
            desc         = parsed_data.get("description", "")
            year         = parsed_data.get("year", "")
            nature       = parsed_data.get("nature", "Manufacturer")
            certs        = ", ".join(parsed_data.get("certifications", [])) or "none found"

            prompt = f"""You are creating website content for a real Indian B2B company.

Company: {company}
Location: {city}, India
Category: {category}
Nature: {nature}
Products found on their IndiaMART page: {products_str}
Established: {year or 'unknown'}
Certifications: {certs}
Existing description: {desc[:300] if desc else 'none'}

Generate a JSON response with:
{{
  "headline": "2-5 word powerful headline for hero section",
  "description": "2 sentence company description specific to their actual products",
  "products": ["clean list of their actual products, max 8, be specific not generic"],
  "usp": ["4 unique selling points specific to this company and their products"],
  "about_story": "3 sentence company story using their real data"
}}

Be specific to their real products. No generic fluff."""

            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Return only valid JSON, no markdown."},
                    {"role": "user",   "content": prompt}
                ],
                max_tokens=600,
                temperature=0.4,
                response_format={"type": "json_object"},
            )

            enriched = json.loads(resp.choices[0].message.content)

            # Merge — keep real scraped products if we got them
            if parsed_data.get("products"):
                enriched["products"] = parsed_data["products"]  # real > AI
            else:
                parsed_data["products"] = enriched.get("products", [])

            parsed_data["headline"]    = enriched.get("headline", "")
            parsed_data["description"] = enriched.get("description", desc)
            parsed_data["usp"]         = enriched.get("usp", [])
            parsed_data["about_story"] = enriched.get("about_story", "")

            print(f"[Enricher] ✅ Enriched {company} | Products: {parsed_data['products'][:3]}")

        except Exception as e:
            print(f"[Enricher] Error: {e}")

        return parsed_data


# ─────────────────────────────────────────────────────────────────────────────
# MAIN: Full pipeline for one lead
# ─────────────────────────────────────────────────────────────────────────────
def crawl_and_enrich(lead):
    """
    Full pipeline:
    1. ScrapingBee fetches real IndiaMART page HTML
    2. Parser extracts all real data
    3. OpenAI enriches and fills gaps
    Returns enriched data dict ready for website generator
    """
    company   = str(lead.get("company") or lead.get("name") or "Company")
    city      = str(lead.get("city") or "India")
    category  = str(lead.get("category") or "Chemicals")
    url       = str(lead.get("indiamart_url") or lead.get("website") or "")

    print(f"\n[Crawler] ━━━ Processing: {company} ━━━")

    result = {
        "company": company, "city": city, "category": category,
        "products": [], "description": "", "year": "2010",
        "phone": str(lead.get("phone") or ""),
        "email": str(lead.get("email") or ""),
        "gst": "", "turnover": "", "employees": "",
        "certifications": [], "nature": "Manufacturer",
        "headline": "", "usp": [], "about_story": "",
    }

    # Step 1: Crawl IndiaMART page
    if url and "indiamart" in url:
        fetcher = ScrapingBeeFetcher()
        html    = fetcher.fetch(url)
        if html:
            parser  = IndiaMArtParser()
            scraped = parser.parse(html, company)
            # Merge scraped data — don't overwrite lead's phone/email if scraper found nothing
            for key, val in scraped.items():
                if val:
                    if key == "phone" and not result["phone"]:
                        result["phone"] = val
                    elif key == "email" and not result["email"]:
                        result["email"] = val
                    else:
                        result[key] = val
    else:
        print(f"[Crawler] No IndiaMART URL for {company} — using SerpAPI fallback")
        # Fall back to SerpAPI search
        from website_generator import RealDataFetcher, ProductExtractor
        fetcher   = RealDataFetcher()
        raw       = fetcher.fetch(company, city, url, category)
        extractor = ProductExtractor()
        result["products"] = extractor.extract(company, category, raw["raw_text"], raw.get("indiamart_snippet",""))
        if not result["phone"] and raw.get("phone"):
            result["phone"] = raw["phone"]
        if not result["email"] and raw.get("email"):
            result["email"] = raw["email"]

    # Step 2: OpenAI enrichment
    enricher = OpenAIEnricher()
    result   = enricher.enrich(company, city, category, result)

    # Step 3: Fallback if still no products
    if not result["products"]:
        from website_generator import ProductExtractor
        result["products"] = ProductExtractor()._fallback(category)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# UPDATED generate_preview_for_lead using real crawler
# ─────────────────────────────────────────────────────────────────────────────
def generate_preview_with_crawler(lead):
    """Drop-in replacement for generate_preview_for_lead using ScrapingBee."""
    from website_generator import WebsiteBuilder, slugify, GENERATED_SITES, BASE_URL
    from datetime import datetime

    # Get real data via crawler
    data = crawl_and_enrich(lead)

    # Build website
    builder = WebsiteBuilder()
    html    = builder.build(
        company     = data["company"],
        city        = data["city"],
        category    = data["category"],
        products    = data["products"],
        description = data["description"] or data.get("about_story",""),
        phone       = data["phone"],
        email       = data["email"],
        year        = data.get("year","2010"),
    )

    slug        = slugify(data["company"])
    preview_url = BASE_URL + "/preview/" + slug

    GENERATED_SITES[slug] = {
        "html": html, "company": data["company"],
        "slug": slug, "lead_id": lead.get("id"),
        "preview_url": preview_url,
        "products": data["products"],
        "created_at": datetime.utcnow().isoformat(),
    }

    # Save to DB
    try:
        from database import get_conn
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(
            "UPDATE leads SET linkedin_url=%s, updated_at=%s WHERE id=%s",
            (preview_url, datetime.utcnow().isoformat(), lead.get("id"))
        )
        conn.commit(); cur.close(); conn.close()
        print(f"[Crawler] ✅ {data['company']} → {preview_url}")
    except Exception as e:
        print(f"[Crawler] DB error: {e}")

    return GENERATED_SITES[slug]
