"""
WEBSITE GENERATOR v4 — SerpAPI + OpenAI Real Product Extraction
================================================================
Since IndiaMART blocks Railway (429/403), we use:
1. SerpAPI → search company name → get real snippet with products
2. OpenAI → extract exact product names from snippet text
3. Build unique website per company with their real products
"""
import os, re, json, requests
from datetime import datetime

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
OPENAI_KEY  = os.getenv("OPENAI_API_KEY", "")
BASE_URL    = os.getenv("WEBHOOK_BASE_URL", "https://web-production-6a55a.up.railway.app")

GENERATED_SITES = {}

INDUSTRY_IMAGES = {
    "Chemicals":           "https://images.unsplash.com/photo-1532187863486-abf9dbad1b69?w=1600&q=80",
    "Food & Beverages":    "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=1600&q=80",
    "Furniture & Home":    "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=1600&q=80",
    "Clothing & Textiles": "https://images.unsplash.com/photo-1558769132-cb1aea458c5e?w=1600&q=80",
    "Electronics":         "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1600&q=80",
    "default":             "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?w=1600&q=80",
}
PRODUCT_ICONS = ["⚗️","🧪","🏭","🔬","💊","🌿","🧴","⚙️","🔩","📦","🧲","🌡️"]


def slugify(t):
    return re.sub(r'[\s_-]+', '-', re.sub(r'[^\w\s-]', '', t.lower().strip()))[:40]


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: Pull real data from SerpAPI (Google knows their products)
# ─────────────────────────────────────────────────────────────────────────────
class RealDataFetcher:

    def fetch(self, company, city, indiamart_url, category):
        """
        Google knows everything about their IndiaMART listing.
        We search for the company and collect ALL text Google has indexed
        from their IndiaMART page — title, snippet, rich results, sitelinks.
        This is the same data that appears when you Google their company name.
        """
        result = {"raw_text": "", "phone": "", "email": "", "indiamart_snippet": ""}

        if not SERPAPI_KEY:
            print("[Fetcher] No SERPAPI_KEY")
            return result

        all_text_parts = []

        # ── Query 1: Search company name directly ─────────────────────────
        # This finds their IndiaMART listing with Google's cached snippet
        # which contains their products as Google indexed them
        try:
            r = requests.get("https://serpapi.com/search", params={
                "q":       f'"{company}" {city} manufacturer supplier products',
                "api_key": SERPAPI_KEY,
                "num":     10,
                "gl":      "in",
                "hl":      "en",
            }, timeout=15)

            if r.status_code == 200:
                data = r.json()

                # Organic results — especially IndiaMART ones have rich product snippets
                for res in data.get("organic_results", []):
                    link    = res.get("link", "")
                    title   = res.get("title", "")
                    snippet = res.get("snippet", "")
                    all_text_parts.append(f"{title}. {snippet}")

                    # IndiaMART snippet is gold — contains actual listed products
                    if "indiamart" in link and snippet:
                        result["indiamart_snippet"] = snippet
                        print(f"[Fetcher] IndiaMART snippet: {snippet[:150]}")

                    # Extract phone/email from snippet
                    for p in re.findall(r'[6-9]\d{9}', snippet):
                        if not result["phone"]:
                            result["phone"] = p
                    for e in re.findall(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', snippet):
                        if not result["email"] and "indiamart" not in e:
                            result["email"] = e

                # Sitelinks — Google shows these for known businesses
                for sl in data.get("organic_results", [{}])[0].get("sitelinks", {}).get("list", []):
                    all_text_parts.append(sl.get("title","") + " " + sl.get("snippet",""))

                # Knowledge graph — best source if it exists
                kg = data.get("knowledge_graph", {})
                if kg:
                    all_text_parts.append(kg.get("description",""))
                    all_text_parts.append(kg.get("type",""))
                    for item in kg.get("attributes", {}).values():
                        all_text_parts.append(str(item))

                print(f"[Fetcher] Query 1: {len(all_text_parts)} text parts collected")

        except Exception as e:
            print(f"[Fetcher] Query 1 error: {e}")

        # ── Query 2: Site-specific search for their products ──────────────
        # Search inside IndiaMART for this specific company — gets product list
        try:
            r2 = requests.get("https://serpapi.com/search", params={
                "q":       f'site:indiamart.com "{company}"',
                "api_key": SERPAPI_KEY,
                "num":     5,
                "gl":      "in",
            }, timeout=15)

            if r2.status_code == 200:
                for res in r2.json().get("organic_results", []):
                    snippet = res.get("snippet", "")
                    title   = res.get("title", "")
                    if snippet:
                        all_text_parts.append(f"{title}. {snippet}")
                        if "indiamart" in res.get("link",""):
                            result["indiamart_snippet"] += " " + snippet

        except Exception as e:
            print(f"[Fetcher] Query 2 error: {e}")

        result["raw_text"] = " | ".join(filter(None, all_text_parts))
        print(f"[Fetcher] Total raw text: {len(result['raw_text'])} chars")
        return result


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: OpenAI extracts exact products from raw Google text
# ─────────────────────────────────────────────────────────────────────────────
class ProductExtractor:

    def extract(self, company, category, raw_text, indiamart_snippet=""):
        """Use OpenAI to pull exact product names from Google's cached text."""

        if not OPENAI_KEY:
            return self._fallback(category)

        # Priority: use IndiaMART snippet if available as it's most accurate
        source_text = (indiamart_snippet + " " + raw_text)[:3000] if raw_text else indiamart_snippet

        if not source_text.strip():
            print(f"[Extractor] No text for {company}, using fallback")
            return self._fallback(category)

        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_KEY)

            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "system",
                    "content": "You extract real product names from business listing text. Return ONLY a JSON array of strings. No explanation."
                }, {
                    "role": "user",
                    "content": f"""Extract the specific products/chemicals/items that "{company}" manufactures or supplies.

Source text (from Google's index of their IndiaMART listing):
{source_text}

Rules:
- Return ONLY products they actually sell, found in the text
- Be specific: "Sodium Hydroxide 98%" not just "chemicals"
- If text mentions "Acid, Alkali, Solvents" list each separately
- 6 to 10 products maximum
- Return as JSON array: ["Product 1", "Product 2", ...]
- If no specific products found in text, return products typical for a {category} company in {company}'s city"""
                }],
                max_tokens=250,
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            content = resp.choices[0].message.content.strip()
            parsed  = json.loads(content)

            # Handle both {"products": [...]} and ["..."] responses
            if isinstance(parsed, list):
                products = parsed
            elif isinstance(parsed, dict):
                products = next((v for v in parsed.values() if isinstance(v, list)), [])
            else:
                products = []

            products = [str(p).strip() for p in products if str(p).strip() and len(str(p)) > 2][:10]

            if products:
                print(f"[Extractor] ✅ Real products for {company}: {products}")
                return products

        except Exception as e:
            print(f"[Extractor] OpenAI error: {e}")

        return self._fallback(category)

    def generate_description(self, company, city, category, products):
        """Unique description per company using their actual products."""
        if not OPENAI_KEY:
            return f"{company} is a trusted {category.lower()} manufacturer based in {city}, India."
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_KEY)
            resp   = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": f"""Write a 2-sentence professional B2B company description for:
Company: {company}
Location: {city}, India
Category: {category}
Key Products: {', '.join(products[:4])}

Be specific to their products. Professional tone. No generic fluff. No quotation marks."""
                }],
                max_tokens=100,
                temperature=0.6,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"[Extractor] Desc error: {e}")
            return f"{company} is a leading {category.lower()} manufacturer and supplier in {city}, India, known for premium quality {products[0] if products else 'products'} and reliable service."

    def _fallback(self, category):
        return {
            "Chemicals":           ["Sodium Hydroxide","Sulphuric Acid","Hydrochloric Acid","Calcium Carbonate","Ferrous Sulphate","Sodium Carbonate","Citric Acid","Potassium Chloride"],
            "Food & Beverages":    ["Packaged Spices","Ready-to-Eat","Beverages","Health Snacks","Organic Products","Dairy Products","Bakery Items","Instant Foods"],
            "Furniture & Home":    ["Wooden Sofa Sets","Modular Kitchen","Bedroom Sets","Office Chairs","Dining Tables","Wardrobes","TV Units","Bookshelves"],
            "Clothing & Textiles": ["Cotton Shirts","Ethnic Wear","Sportswear","School Uniforms","Fabric Rolls","Sarees","Kurtis","Denim Jeans"],
            "Electronics":         ["Control Panels","PCB Boards","LED Drivers","Power Transformers","Wiring Harness","Sensors","Relays","Circuit Breakers"],
        }.get(category, ["Product A","Product B","Product C","Product D","Product E","Product F"])


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: Build the full premium HTML website
# ─────────────────────────────────────────────────────────────────────────────
class WebsiteBuilder:

    def build(self, company, city, category, products, description, phone, email, year="2010"):
        slug    = slugify(company)
        letter  = company[0].upper()
        wa      = f"https://wa.me/91{phone}" if phone else "#contact"
        phone_d = phone if phone else "+91 XXXXX XXXXX"
        email_d = email if email else f"info@{slug}.com"
        img     = INDUSTRY_IMAGES.get(category, INDUSTRY_IMAGES["default"])
        maps_q  = requests.utils.quote(f"{company} {city} India")

        prod_cards = ""
        for i, p in enumerate(products[:8]):
            icon = PRODUCT_ICONS[i % len(PRODUCT_ICONS)]
            prod_cards += f"""
            <div class="pc">
                <div class="pc-icon">{icon}</div>
                <h3>{p}</h3>
                <p>Premium quality {p} manufactured to BIS/ISO standards. Available in custom grades and bulk quantities with complete quality documentation.</p>
                <ul class="pc-specs">
                    <li>✓ Custom specifications available</li>
                    <li>✓ Bulk & retail quantities</li>
                    <li>✓ Quality certificate provided</li>
                </ul>
                <a href="#contact" class="pc-link">Get Quote →</a>
            </div>"""

        testimonials = [
            ("Suresh Mehta",  "Mehta Industries, Delhi",    f"Best quality {products[0]} I've sourced in years. Timely delivery, excellent packaging, no complaints."),
            ("Anita Sharma",  "Sharma Chemicals, Mumbai",   f"4 years of partnership with {company}. Never had a quality issue. Truly reliable supplier."),
            ("Vikram Singh",  "Singh Manufacturing, Surat", f"Switched to {company} and saved 20% on procurement while getting better quality. Highly recommend."),
        ]
        testi_html = "".join(f"""
        <div class="tc">
            <div class="stars">★★★★★</div>
            <p>"{t}"</p>
            <div class="ta"><div class="tav">{n[0]}</div>
            <div><strong>{n}</strong><span>{c}</span></div></div>
        </div>""" for n, c, t in testimonials)

        ind_chips   = self._industries(category)
        ind_html    = "".join(f'<div class="ic">{x}</div>' for x in ind_chips)
        prod_opts   = "".join(f"<option>{p}</option>" for p in products)
        prod_footer = "".join(f'<li><a href="#products">{p}</a></li>' for p in products[:5])

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{company} — {category} Manufacturer in {city} | Quality Supplier India</title>
<meta name="description" content="{description[:155]}">
<meta name="keywords" content="{company}, {', '.join(products[:3])}, {category}, {city}, manufacturer, supplier, bulk India">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Playfair+Display:ital,wght@0,700;1,600&display=swap" rel="stylesheet">
<style>
:root{{--navy:#0c1e35;--blue:#1e4d8c;--gold:#d4891a;--gold2:#f0b040;--lt:#f6f8fb;--w:#fff;--gr:#5a6a7a;--br:#dde4ed;--gn:#15803d}}
*{{margin:0;padding:0;box-sizing:border-box}}html{{scroll-behavior:smooth}}
body{{font-family:'Plus Jakarta Sans',sans-serif;color:var(--navy);background:var(--w)}}a{{text-decoration:none}}
.pb{{position:fixed;top:0;left:0;right:0;z-index:9999;background:linear-gradient(90deg,#6d28d9,#4338ca);color:#fff;text-align:center;padding:10px 20px;font-size:0.8rem;display:flex;align-items:center;justify-content:center;gap:14px}}
.pb strong{{color:#fcd34d}}.pb a{{background:#fcd34d;color:#312e81;padding:4px 14px;border-radius:20px;font-weight:700;font-size:0.75rem}}
nav{{position:fixed;top:40px;width:100%;z-index:100;background:rgba(12,30,53,0.97);backdrop-filter:blur(20px);height:66px;display:flex;align-items:center;justify-content:space-between;padding:0 6%;border-bottom:1px solid rgba(212,137,26,0.2);transition:top .3s,box-shadow .3s}}
.nl{{display:flex;align-items:center;gap:12px}}.lm{{width:40px;height:40px;background:var(--gold);border-radius:9px;display:flex;align-items:center;justify-content:center;font-family:'Playfair Display',serif;font-size:1.25rem;color:var(--navy);font-weight:700}}
.nb{{color:#fff;font-weight:700;font-size:.95rem;line-height:1.2}}.nb small{{display:block;font-size:.68rem;color:rgba(255,255,255,.4);font-weight:400}}
.nls{{display:flex;gap:26px;list-style:none}}.nls a{{color:rgba(255,255,255,.65);font-size:.86rem;font-weight:500;transition:color .2s}}.nls a:hover{{color:var(--gold)}}
.ncta{{background:var(--gold);color:var(--navy);padding:9px 20px;border-radius:8px;font-weight:700;font-size:.84rem;transition:all .2s}}.ncta:hover{{background:var(--gold2);transform:translateY(-1px)}}
.hero{{min-height:100vh;padding:150px 6% 80px;background:linear-gradient(140deg,rgba(12,30,53,.96) 0%,rgba(30,77,140,.92) 100%),url('{img}')center/cover no-repeat;display:flex;align-items:center;position:relative}}
.hero::after{{content:'';position:absolute;bottom:0;left:0;right:0;height:80px;background:linear-gradient(transparent,var(--w))}}
.hc{{position:relative;z-index:1;max-width:700px}}
.htag{{display:inline-flex;align-items:center;gap:8px;background:rgba(212,137,26,.15);border:1px solid rgba(212,137,26,.4);color:var(--gold);padding:6px 16px;border-radius:99px;font-size:.75rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;margin-bottom:22px}}
.hero h1{{font-family:'Playfair Display',serif;font-size:clamp(2.2rem,5vw,3.8rem);color:#fff;line-height:1.15;margin-bottom:18px}}
.hero h1 em{{color:var(--gold);font-style:italic}}
.hero p{{color:rgba(255,255,255,.7);font-size:1.05rem;line-height:1.75;margin-bottom:36px;max-width:580px}}
.hbtns{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:50px}}
.bg{{background:var(--gold);color:var(--navy);padding:14px 32px;border-radius:10px;font-weight:800;font-size:.93rem;transition:all .25s;display:inline-flex;align-items:center;gap:8px}}.bg:hover{{background:var(--gold2);transform:translateY(-2px);box-shadow:0 8px 28px rgba(212,137,26,.45)}}
.bw{{border:1.5px solid rgba(255,255,255,.3);color:#fff;padding:14px 32px;border-radius:10px;font-weight:500;font-size:.93rem;transition:all .25s;display:inline-flex;align-items:center;gap:8px}}.bw:hover{{border-color:var(--gold);color:var(--gold)}}
.hst{{display:flex;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12);border-radius:14px;overflow:hidden;width:fit-content}}
.hs{{padding:18px 28px;text-align:center;border-right:1px solid rgba(255,255,255,.1)}}.hs:last-child{{border-right:none}}
.hsn{{font-family:'Playfair Display',serif;font-size:1.8rem;color:var(--gold);font-weight:700}}.hsl{{color:rgba(255,255,255,.45);font-size:.72rem;margin-top:2px}}
.sec{{padding:88px 6%}}.lt{{background:var(--lt)}}.dk{{background:var(--navy)}}
.ey{{display:inline-block;background:rgba(212,137,26,.12);color:var(--gold);padding:5px 14px;border-radius:99px;font-size:.7rem;font-weight:800;letter-spacing:.09em;text-transform:uppercase;margin-bottom:10px}}
.st{{font-family:'Playfair Display',serif;font-size:clamp(1.8rem,3.5vw,2.6rem);line-height:1.2;margin-bottom:12px}}.dk .st{{color:#fff}}
.ss{{color:var(--gr);font-size:.98rem;line-height:1.7;max-width:560px;margin-bottom:48px}}.dk .ss{{color:rgba(255,255,255,.45)}}
.ag{{display:grid;grid-template-columns:1fr 1fr;gap:60px;align-items:center}}
.afs{{display:grid;gap:12px;margin-top:24px}}
.af{{display:flex;gap:14px;align-items:flex-start;background:var(--w);padding:16px 18px;border-radius:10px;border:1px solid var(--br);transition:all .2s}}.af:hover{{border-color:var(--gold);transform:translateX(4px)}}
.afi{{width:42px;height:42px;background:rgba(212,137,26,.1);border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:1.15rem;flex-shrink:0}}
.af h4{{font-weight:700;font-size:.9rem;margin-bottom:3px}}.af p{{color:var(--gr);font-size:.8rem;line-height:1.5}}
.av{{background:linear-gradient(150deg,var(--navy),var(--blue));border-radius:18px;padding:44px 32px;text-align:center;color:#fff;position:relative;overflow:hidden}}
.av::before{{content:'';position:absolute;top:-50px;right:-50px;width:200px;height:200px;border-radius:50%;background:rgba(212,137,26,.07)}}
.blogo{{width:88px;height:88px;background:var(--gold);border-radius:18px;display:flex;align-items:center;justify-content:center;font-family:'Playfair Display',serif;font-size:2.8rem;color:var(--navy);font-weight:700;margin:0 auto 18px}}
.av h3{{font-family:'Playfair Display',serif;font-size:1.4rem;margin-bottom:6px}}.av p{{color:rgba(255,255,255,.5);font-size:.85rem;margin-bottom:18px}}
.bds{{display:flex;gap:8px;justify-content:center;flex-wrap:wrap}}.bd{{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.15);padding:5px 12px;border-radius:99px;font-size:.72rem;color:rgba(255,255,255,.75)}}
.tl{{margin-top:24px;text-align:left;position:relative}}.tl::before{{content:'';position:absolute;left:58px;top:0;bottom:0;width:2px;background:rgba(255,255,255,.1)}}
.ti{{display:flex;gap:16px;padding:12px 0}}.ty{{min-width:50px;font-weight:800;color:var(--gold);font-size:.82rem;text-align:right;padding-top:3px}}
.tc2{{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);border-radius:8px;padding:10px 14px;flex:1;margin-left:12px}}
.tc2 h4{{font-weight:700;font-size:.82rem;color:#fff;margin-bottom:2px}}.tc2 p{{color:rgba(255,255,255,.4);font-size:.74rem}}
.pg{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:22px}}
.pc{{border:1px solid var(--br);border-radius:14px;padding:28px 22px;background:var(--w);transition:all .25s;position:relative;overflow:hidden}}
.pc::after{{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--gold),transparent);transform:scaleX(0);transform-origin:left;transition:transform .3s}}
.pc:hover{{transform:translateY(-5px);box-shadow:0 20px 48px rgba(12,30,53,.1);border-color:var(--gold)}}.pc:hover::after{{transform:scaleX(1)}}
.pc-icon{{font-size:2rem;margin-bottom:14px}}.pc h3{{font-weight:700;font-size:.97rem;margin-bottom:9px}}.pc p{{color:var(--gr);font-size:.81rem;line-height:1.6;margin-bottom:12px}}
.pc-specs{{list-style:none;margin-bottom:16px}}.pc-specs li{{font-size:.78rem;color:var(--gn);padding:2px 0;font-weight:600}}
.pc-link{{color:var(--gold);font-weight:700;font-size:.82rem}}.pc-link:hover{{text-decoration:underline}}
.ig{{display:flex;flex-wrap:wrap;gap:10px;margin-top:8px}}.ic{{background:var(--w);border:1.5px solid var(--br);border-radius:9px;padding:12px 18px;font-weight:600;font-size:.85rem;transition:all .2s}}.ic:hover{{border-color:var(--gold);background:rgba(212,137,26,.05);transform:translateY(-2px)}}
.qg{{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}}.qc{{background:var(--w);border:1px solid var(--br);border-radius:12px;padding:22px 18px;text-align:center}}
.qn{{font-family:'Playfair Display',serif;font-size:2rem;color:var(--gold);font-weight:700}}.ql{{color:var(--gr);font-size:.8rem;margin-top:3px}}
.wg{{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}}
.wc{{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:13px;padding:28px 22px;text-align:center;transition:all .25s}}.wc:hover{{background:rgba(212,137,26,.08);border-color:rgba(212,137,26,.3)}}
.wi{{font-size:2.4rem;margin-bottom:14px}}.wc h3{{color:#fff;font-weight:700;font-size:.95rem;margin-bottom:9px}}.wc p{{color:rgba(255,255,255,.5);font-size:.81rem;line-height:1.6}}
.tg{{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:20px}}
.tc{{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);border-radius:13px;padding:26px 22px}}
.stars{{color:var(--gold);font-size:.95rem;letter-spacing:3px;margin-bottom:12px}}.tc p{{color:rgba(255,255,255,.72);font-size:.86rem;line-height:1.7;margin-bottom:18px;font-style:italic}}
.ta{{display:flex;align-items:center;gap:11px}}.tav{{width:40px;height:40px;background:var(--gold);border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;color:var(--navy);font-size:.95rem}}
.ta strong{{color:#fff;font-size:.86rem;display:block}}.ta span{{color:rgba(255,255,255,.38);font-size:.73rem}}
.ctab{{background:linear-gradient(135deg,var(--gold),var(--gold2));padding:70px 6%;text-align:center}}
.ctab h2{{font-family:'Playfair Display',serif;font-size:clamp(1.8rem,3.5vw,2.5rem);color:var(--navy);margin-bottom:12px}}
.ctab p{{color:rgba(12,30,53,.65);font-size:.98rem;margin-bottom:28px;max-width:500px;margin-inline:auto}}
.bd2{{background:var(--navy);color:#fff;padding:14px 34px;border-radius:10px;font-weight:700;font-size:.93rem;display:inline-flex;align-items:center;gap:8px;transition:all .2s}}.bd2:hover{{transform:translateY(-2px);box-shadow:0 8px 28px rgba(12,30,53,.3)}}
.cg{{display:grid;grid-template-columns:1fr 1.2fr;gap:52px;align-items:start}}
.cis{{display:grid;gap:14px}}.ci{{display:flex;gap:14px;align-items:flex-start;background:var(--lt);padding:18px;border-radius:11px;border:1px solid var(--br)}}
.cic{{width:44px;height:44px;background:var(--navy);border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:1rem;flex-shrink:0}}
.ci h4{{font-weight:700;font-size:.86rem;margin-bottom:3px}}.ci p,.ci a{{color:var(--gr);font-size:.83rem}}.ci a{{color:var(--blue);font-weight:600}}
.mw{{border-radius:11px;overflow:hidden;height:175px;margin-top:14px;border:1px solid var(--br)}}.mw iframe{{width:100%;height:100%;border:none}}
.cf{{background:var(--lt);border-radius:16px;padding:36px;border:1px solid var(--br)}}.cft{{font-family:'Playfair Display',serif;font-size:1.45rem;margin-bottom:22px}}
.fg{{margin-bottom:14px}}.fg label{{display:block;font-size:.78rem;font-weight:700;color:var(--navy);margin-bottom:5px;letter-spacing:.02em}}
.fg input,.fg textarea,.fg select{{width:100%;padding:11px 14px;border:1.5px solid var(--br);border-radius:9px;font-family:'Plus Jakarta Sans',sans-serif;font-size:.88rem;color:var(--navy);background:var(--w);outline:none;transition:border-color .2s}}
.fg input:focus,.fg textarea:focus,.fg select:focus{{border-color:var(--gold)}}.fg textarea{{height:105px;resize:none}}
.fgr{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.sub{{width:100%;background:var(--navy);color:#fff;padding:13px;border:none;border-radius:9px;font-size:.93rem;font-weight:700;cursor:pointer;transition:all .2s;font-family:'Plus Jakarta Sans',sans-serif}}.sub:hover{{background:var(--gold);color:var(--navy)}}
.footer{{background:var(--navy);padding:48px 6% 24px}}.fg2{{display:grid;grid-template-columns:2fr 1fr 1fr;gap:44px;margin-bottom:32px}}
.fbp{{color:rgba(255,255,255,.4);font-size:.82rem;line-height:1.7;max-width:280px;margin-top:12px}}
.footer h4{{color:#fff;font-weight:700;font-size:.88rem;margin-bottom:14px}}.footer ul{{list-style:none}}.footer ul li{{margin-bottom:8px}}.footer ul li a{{color:rgba(255,255,255,.4);font-size:.8rem;transition:color .2s}}.footer ul li a:hover{{color:var(--gold)}}
.fb{{border-top:1px solid rgba(255,255,255,.08);padding-top:22px;display:flex;justify-content:space-between;align-items:center;color:rgba(255,255,255,.28);font-size:.76rem}}.fb a{{color:var(--gold);font-weight:600}}
.fact{{display:flex;gap:10px;margin-top:14px}}.fact a{{padding:7px 14px;border-radius:7px;font-size:.78rem;font-weight:600}}
.wa{{position:fixed;bottom:26px;right:26px;z-index:998;background:#25d366;color:#fff;width:58px;height:58px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1.65rem;box-shadow:0 6px 24px rgba(37,211,102,.45);transition:all .2s}}.wa:hover{{transform:scale(1.12)}}
.wtt{{position:fixed;bottom:41px;right:93px;z-index:997;background:var(--navy);color:#fff;padding:7px 14px;border-radius:7px;font-size:.78rem;font-weight:500;white-space:nowrap;box-shadow:0 4px 12px rgba(0,0,0,.15);pointer-events:none}}
@media(max-width:900px){{.ag,.cg,.wg,.fg2{{grid-template-columns:1fr}}.qg{{grid-template-columns:repeat(2,1fr)}}.nls{{display:none}}.hero h1{{font-size:2rem}}}}
</style></head><body>

<div class="pb">🎨 <strong>Free Sample Website</strong> built for {company} by DigitalBoost Agency &nbsp;·&nbsp; <a href="#contact">Get Your Real Website →</a></div>

<nav id="nav">
  <div class="nl"><div class="lm">{letter}</div><div class="nb">{company}<small>{category} · {city}</small></div></div>
  <ul class="nls"><li><a href="#about">About</a></li><li><a href="#products">Products</a></li><li><a href="#why-us">Why Us</a></li><li><a href="#quality">Quality</a></li><li><a href="#contact">Contact</a></li></ul>
  <a href="{wa}" class="ncta">📱 Get Quote</a>
</nav>

<section class="hero">
  <div class="hc">
    <div class="htag">⚡ {city}, India · Trusted Since {year}</div>
    <h1>Leading <em>{products[0] if products else category}</em><br>Manufacturer & Supplier</h1>
    <p>{description}</p>
    <div class="hbtns"><a href="#products" class="bg">🏭 View Our Products</a><a href="{wa}" class="bw">💬 WhatsApp Now</a></div>
    <div class="hst">
      <div class="hs"><div class="hsn">500+</div><div class="hsl">Clients</div></div>
      <div class="hs"><div class="hsn">{len(products)}</div><div class="hsl">Products</div></div>
      <div class="hs"><div class="hsn">25+</div><div class="hsl">States</div></div>
      <div class="hs"><div class="hsn">Est.{year}</div><div class="hsl">Founded</div></div>
    </div>
  </div>
</section>

<section class="sec lt" id="about">
  <div class="ag">
    <div>
      <div class="ey">About Us</div>
      <h2 class="st">Built on Trust.<br>Driven by Quality.</h2>
      <p style="color:var(--gr);line-height:1.75;margin-bottom:24px">{description}</p>
      <div class="afs">
        <div class="af"><div class="afi">🏆</div><div><h4>Industry Expertise</h4><p>Deep domain knowledge in {category.lower()} manufacturing</p></div></div>
        <div class="af"><div class="afi">🚚</div><div><h4>PAN India Delivery</h4><p>Reliable logistics covering all major cities and states</p></div></div>
        <div class="af"><div class="afi">🤝</div><div><h4>Bulk Order Ready</h4><p>Custom pricing and flexible terms for large volume</p></div></div>
        <div class="af"><div class="afi">📋</div><div><h4>Full Compliance</h4><p>ISO certified, GST registered, all documents provided</p></div></div>
      </div>
    </div>
    <div class="av">
      <div class="blogo">{letter}</div>
      <h3>{company}</h3><p>{city}, India · Est. {year}</p>
      <div class="bds"><span class="bd">✓ GST Verified</span><span class="bd">✓ ISO Compliant</span><span class="bd">✓ Bulk Ready</span></div>
      <div class="tl">
        <div class="ti"><div class="ty">{year}</div><div class="tc2"><h4>Founded</h4><p>Started with a vision for quality</p></div></div>
        <div class="ti"><div class="ty">{int(year)+3}</div><div class="tc2"><h4>ISO Certified</h4><p>Achieved international quality standards</p></div></div>
        <div class="ti"><div class="ty">{int(year)+7}</div><div class="tc2"><h4>500+ Clients</h4><p>Expanded PAN India operations</p></div></div>
        <div class="ti"><div class="ty">Now</div><div class="tc2"><h4>Market Leader</h4><p>Trusted across 25 states nationwide</p></div></div>
      </div>
    </div>
  </div>
</section>

<section class="sec" id="products">
  <div class="ey">Our Products</div>
  <h2 class="st">What We Manufacture</h2>
  <p class="ss">Every product manufactured to BIS/ISO standards with full quality documentation. Custom specifications and bulk quantities available on request.</p>
  <div class="pg">{prod_cards}</div>
</section>

<section class="sec lt" id="industries">
  <div class="ey">Industries Served</div>
  <h2 class="st">Who We Supply To</h2>
  <p class="ss">Our products are trusted across a wide range of industries throughout India.</p>
  <div class="ig">{ind_html}</div>
</section>

<section class="sec" id="quality">
  <div class="ey">Quality Assurance</div>
  <h2 class="st">Our Quality Promise</h2>
  <p class="ss">Every batch tested and certified before dispatch. We maintain strict quality control throughout our manufacturing process.</p>
  <div class="qg">
    <div class="qc"><div class="qn">100%</div><div class="ql">Quality Tested</div></div>
    <div class="qc"><div class="qn">ISO</div><div class="ql">Certified</div></div>
    <div class="qc"><div class="qn">500+</div><div class="ql">Happy Clients</div></div>
    <div class="qc"><div class="qn">24hr</div><div class="ql">Response Time</div></div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-top:22px">
    <div class="af"><div class="afi">🔬</div><div><h4>Lab Testing</h4><p>Every batch tested before dispatch</p></div></div>
    <div class="af"><div class="afi">📄</div><div><h4>CoA & MSDS</h4><p>Full certificates for every product</p></div></div>
    <div class="af"><div class="afi">♻️</div><div><h4>Sustainable</h4><p>Eco-friendly manufacturing practices</p></div></div>
  </div>
</section>

<section class="sec dk" id="why-us">
  <div class="ey">Why Choose Us</div>
  <h2 class="st">The {company} Advantage</h2>
  <p class="ss">Here's why 500+ businesses across India trust us as their preferred supplier.</p>
  <div class="wg">
    <div class="wc"><div class="wi">⚡</div><h3>Fast Turnaround</h3><p>Order processing and dispatch within 24–48 hours of confirmation</p></div>
    <div class="wc"><div class="wi">💰</div><h3>Competitive Pricing</h3><p>Factory-direct rates with bulk discounts and flexible payment terms</p></div>
    <div class="wc"><div class="wi">🎯</div><h3>Custom Specs</h3><p>Products made to your exact grade, purity and packaging needs</p></div>
    <div class="wc"><div class="wi">🏆</div><h3>Certified Quality</h3><p>ISO-compliant process, certificates available for every batch</p></div>
    <div class="wc"><div class="wi">🚚</div><h3>PAN India Delivery</h3><p>Reliable logistics covering all 28 states and union territories</p></div>
    <div class="wc"><div class="wi">📞</div><h3>Dedicated Support</h3><p>Single point of contact for orders, queries and after-sales</p></div>
  </div>
</section>

<section class="sec dk" id="testimonials" style="padding-top:0">
  <div class="ey">Client Reviews</div>
  <h2 class="st">What Our Clients Say</h2>
  <p class="ss">Trusted by businesses of all sizes across India for consistent quality.</p>
  <div class="tg">{testi_html}</div>
</section>

<div class="ctab">
  <h2>Ready to Place Your Order?</h2>
  <p>Get a custom quote, product specs or bulk pricing within 2 hours.</p>
  <a href="#contact" class="bd2">📩 Request a Quote Now</a>
</div>

<section class="sec" id="contact">
  <div class="ey">Contact Us</div>
  <h2 class="st">Get In Touch</h2>
  <p class="ss">Fill the form or WhatsApp us directly. We respond within 2 hours during business hours.</p>
  <div class="cg">
    <div class="cis">
      <div class="ci"><div class="cic">📍</div><div><h4>Location</h4><p>{city}, India</p></div></div>
      <div class="ci"><div class="cic">📱</div><div><h4>Phone / WhatsApp</h4><p><a href="{wa}">{phone_d}</a></p></div></div>
      <div class="ci"><div class="cic">📧</div><div><h4>Email</h4><p><a href="mailto:{email_d}">{email_d}</a></p></div></div>
      <div class="ci"><div class="cic">🕒</div><div><h4>Business Hours</h4><p>Mon–Sat: 9:00 AM – 6:30 PM IST</p></div></div>
      <div class="mw"><iframe src="https://maps.google.com/maps?q={maps_q}&output=embed" allowfullscreen loading="lazy"></iframe></div>
    </div>
    <div class="cf">
      <h3 class="cft">Send an Enquiry</h3>
      <div class="fgr"><div class="fg"><label>Name *</label><input type="text" placeholder="Rajesh Kumar"></div><div class="fg"><label>Company</label><input type="text" placeholder="Kumar Industries"></div></div>
      <div class="fgr"><div class="fg"><label>Phone *</label><input type="tel" placeholder="+91 98765 43210"></div><div class="fg"><label>Email</label><input type="email" placeholder="rajesh@company.com"></div></div>
      <div class="fg"><label>Product Required *</label><select><option value="">Select product...</option>{prod_opts}<option>Other / Custom Requirement</option></select></div>
      <div class="fg"><label>Quantity Required</label><input type="text" placeholder="e.g. 500 kg, 1 tonne, 100 units"></div>
      <div class="fg"><label>Message / Specifications</label><textarea placeholder="Describe your requirement, delivery location, timeline..."></textarea></div>
      <button class="sub" onclick="this.textContent='✓ Sent! We will contact you within 2 hours.';this.style.background='#15803d';setTimeout(()=>{{this.textContent='Send Enquiry →';this.style.background=''}},5000)">Send Enquiry →</button>
    </div>
  </div>
</section>

<footer class="footer">
  <div class="fg2">
    <div><div class="lm">{letter}</div><p class="fbp">{description[:130]}...</p>
    <div class="fact"><a href="{wa}" style="background:#25d366;color:#fff">💬 WhatsApp</a><a href="tel:+91{phone}" style="background:#1e4d8c;color:#fff">📞 Call</a></div></div>
    <div><h4>Quick Links</h4><ul><li><a href="#about">About Us</a></li><li><a href="#products">Products</a></li><li><a href="#why-us">Why Us</a></li><li><a href="#quality">Quality</a></li><li><a href="#contact">Contact</a></li></ul></div>
    <div><h4>Products</h4><ul>{prod_footer}</ul></div>
  </div>
  <div class="fb"><span>© 2024 <strong style="color:rgba(255,255,255,.65)">{company}</strong> · {city}, India</span><span>Website by <a href="#contact">DigitalBoost Agency</a></span></div>
</footer>

<a href="{wa}" class="wa" target="_blank">💬</a>
<div class="wtt">Chat on WhatsApp</div>

<script>
window.addEventListener('scroll',()=>{{const n=document.getElementById('nav');if(window.scrollY>50){{n.style.top='0';n.style.boxShadow='0 4px 24px rgba(0,0,0,.3)'}}else{{n.style.top='40px';n.style.boxShadow='none'}}}});
document.querySelectorAll('a[href^="#"]').forEach(a=>{{a.addEventListener('click',e=>{{const el=document.querySelector(a.getAttribute('href'));if(el){{e.preventDefault();el.scrollIntoView({{behavior:'smooth'}})}}}});}});
const io=new IntersectionObserver(entries=>entries.forEach(e=>{{if(e.isIntersecting){{e.target.style.opacity='1';e.target.style.transform='translateY(0)'}}}}){{threshold:0.1}});
document.querySelectorAll('.pc,.wc,.tc,.af,.qc,.ic').forEach(el=>{{el.style.opacity='0';el.style.transform='translateY(18px)';el.style.transition='opacity 0.5s,transform 0.5s';io.observe(el)}});
</script>
</body></html>"""

    def _industries(self, cat):
        return {{
            "Chemicals":           ["🏭 Manufacturing","🌾 Agriculture","💊 Pharmaceuticals","🏗 Construction","🚗 Automotive","🍽 Food Processing","👗 Textile","⚡ Energy"],
            "Food & Beverages":    ["🏪 Retail","🏨 Hotels","🏥 Healthcare","🎓 Institutions","✈️ Airlines","🛒 E-Commerce","🏬 Supermarkets","🎪 Events"],
            "Furniture & Home":    ["🏠 Residential","🏢 Commercial","🏨 Hospitality","🏥 Healthcare","🎓 Education","🏭 Industrial","🏛 Government","✈️ Hospitality"],
            "Clothing & Textiles": ["🛒 Retail","🏭 Manufacturing","🎓 Education","🏥 Healthcare","🏨 Hospitality","⚽ Sports","🎭 Entertainment","🏢 Corporate"],
            "Electronics":         ["🏭 Manufacturing","🏥 Healthcare","🏗 Construction","🚗 Automotive","⚡ Power","📡 Telecom","🏢 Commercial","🎓 Education"],
        }}.get(cat, ["🏭 Manufacturing","🏥 Healthcare","🏗 Construction","🚗 Automotive","⚡ Energy","📡 Telecom","🏢 Commercial","🎓 Education"])


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
def generate_preview_for_lead(lead):
    company   = lead.get("company") or lead.get("name") or "Company"
    city      = lead.get("city") or "India"
    indiamart = lead.get("indiamart_url") or lead.get("website") or ""
    category  = lead.get("category") or "Chemicals"

    print(f"[Preview] Generating for: {company}")

    # Step 1: Fetch real data via SerpAPI
    fetcher = RealDataFetcher()
    raw     = fetcher.fetch(company, city, indiamart, category)

    phone = raw.get("phone") or str(lead.get("phone") or "")
    email = raw.get("email") or str(lead.get("email") or "")

    # Step 2: Extract real products with OpenAI
    extractor = ProductExtractor()
    products  = extractor.extract(company, category, raw["raw_text"], raw.get("indiamart_snippet",""))
    desc      = extractor.generate_description(company, city, category, products)

    # Step 3: Build website
    slug    = slugify(company)
    builder = WebsiteBuilder()
    html    = builder.build(company, city, category, products, desc, phone, email)

    preview_url = BASE_URL + "/preview/" + slug
    GENERATED_SITES[slug] = {
        "html": html, "company": company, "slug": slug,
        "lead_id": lead.get("id"), "preview_url": preview_url,
        "products": products,
        "created_at": datetime.utcnow().isoformat(),
    }

    # Save preview URL back to leads DB
    try:
        from database import get_conn
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(
            "UPDATE leads SET linkedin_url=%s, updated_at=%s WHERE id=%s",
            (preview_url, datetime.utcnow().isoformat(), lead.get("id"))
        )
        conn.commit(); cur.close(); conn.close()
        print(f"[Preview] ✅ {company} → {preview_url}")
        print(f"[Preview] Products: {products}")
    except Exception as e:
        print(f"[Preview] DB error: {e}")

    return GENERATED_SITES[slug]
