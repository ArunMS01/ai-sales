"""
WEBSITE GENERATOR v2
=====================
Generates a full multi-page, conversion-optimized website
for each IndiaMART lead and hosts it on Railway.

Access: /preview/{slug}
Pages:  Home, About, Products, Why Us, Contact
"""
import os
import re
import json
import time
import requests
from datetime import datetime

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
BASE_URL    = os.getenv("WEBHOOK_BASE_URL", "https://web-production-6a55a.up.railway.app")

# In-memory store {slug: {"html": ..., "company": ..., ...}}
GENERATED_SITES = {}

UNSPLASH_INDUSTRY = {
    "Chemicals":          "https://images.unsplash.com/photo-1532187863486-abf9dbad1b69?w=1600&q=80",
    "Food & Beverages":   "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=1600&q=80",
    "Furniture & Home":   "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=1600&q=80",
    "Clothing & Textiles":"https://images.unsplash.com/photo-1558769132-cb1aea458c5e?w=1600&q=80",
    "Electronics":        "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1600&q=80",
    "default":            "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?w=1600&q=80",
}

PRODUCT_ICONS = ["⚗️","🧪","🏭","🔬","💊","🌿","🧴","⚙️","🔩","📦","🧲","🌡️"]


def slugify(text):
    text = re.sub(r'[^\w\s-]', '', text.lower().strip())
    return re.sub(r'[\s_-]+', '-', text)[:40]


class IndiaMArtScraper:
    HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    def scrape(self, url, company, city, products_hint="", category="Chemicals"):
        data = {
            "company": company, "city": city, "category": category,
            "products": [], "description": "", "phone": "",
            "email": "", "year": "", "letter": (company[0].upper() if company else "C"),
            "hero_img": UNSPLASH_INDUSTRY.get(category, UNSPLASH_INDUSTRY["default"]),
        }
        if url and "indiamart" in url:
            try:
                r = requests.get(url, headers=self.HEADERS, timeout=12)
                if r.status_code == 200:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(r.text, "html.parser")
                    text = soup.get_text(" ", strip=True)
                    # Products
                    for el in soup.find_all(True, class_=re.compile(r"product|item|catalog", re.I))[:12]:
                        name = el.get_text(strip=True)[:60]
                        if name and len(name) > 3 and name not in data["products"]:
                            data["products"].append(name)
                    # Description
                    desc = soup.find(class_=re.compile(r"about|description|overview", re.I))
                    if desc:
                        data["description"] = desc.get_text(" ", strip=True)[:400]
                    # Phone
                    for p in re.findall(r'[6-9]\d{9}', text):
                        if p not in ["9696969696","8888888888"]:
                            data["phone"] = p; break
                    # Email
                    for e in re.findall(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', text):
                        if "indiamart" not in e and len(e) < 60:
                            data["email"] = e; break
                    # Year
                    m = re.search(r'(?:est|since|founded)[^\d]*(\d{4})', text, re.I)
                    if m: data["year"] = m.group(1)
            except Exception as ex:
                print("[Scraper] " + str(ex)[:60])

        if not data["products"]:
            data["products"] = self._defaults(category)
        return data

    def _defaults(self, cat):
        defaults = {
            "Chemicals":           ["Industrial Chemicals","Agricultural Chemicals","Cleaning Chemicals","Paint Chemicals","Water Treatment Chemicals","Pharmaceutical Chemicals","Specialty Chemicals","Lab Reagents"],
            "Food & Beverages":    ["Packaged Foods","Beverages","Spices & Condiments","Snacks","Health Foods","Organic Products","Dairy Products","Bakery Items"],
            "Furniture & Home":    ["Wooden Furniture","Modular Furniture","Home Decor","Sofa Sets","Bedroom Furniture","Office Furniture","Storage Solutions","Outdoor Furniture"],
            "Clothing & Textiles": ["Men's Wear","Women's Wear","Ethnic Wear","Sportswear","Fabric & Textiles","Uniforms","Designer Wear","Kids Clothing"],
            "Electronics":         ["Electronic Components","LED Lighting","Power Supplies","Circuit Boards","Sensors","Cables & Wires","Control Systems","Testing Equipment"],
        }
        return defaults.get(cat, ["Product 1","Product 2","Product 3","Product 4","Product 5","Product 6"])


class WebsiteGenerator:

    def generate(self, data, slug):
        company  = data["company"]
        city     = data["city"]
        category = data.get("category","Manufacturer")
        products = data.get("products", [])[:8]
        desc     = data.get("description","") or f"{company} is a trusted manufacturer and supplier based in {city}, India. We deliver premium quality products with consistency, reliability and excellent customer service to clients across India."
        phone    = data.get("phone","") or ""
        email    = data.get("email","") or f"info@{slug}.com"
        year     = data.get("year","") or "2010"
        letter   = data["letter"]
        hero_img = data["hero_img"]
        wa_link  = f"https://wa.me/91{phone}" if phone else "#contact"
        phone_d  = phone if phone else "+91 XXXXX XXXXX"
        maps_q   = requests.utils.quote(company + " " + city + " India")

        # Build sections HTML
        products_cards = ""
        for i, p in enumerate(products):
            icon = PRODUCT_ICONS[i % len(PRODUCT_ICONS)]
            products_cards += f"""
            <div class="prod-card" data-aos="fade-up" data-aos-delay="{i*80}">
                <div class="prod-icon">{icon}</div>
                <h3>{p}</h3>
                <p>High-quality {p.lower()} manufactured to IS/ISO standards. Available in custom specifications for bulk orders.</p>
                <ul class="prod-specs">
                    <li>✓ Custom specifications</li>
                    <li>✓ Bulk quantity available</li>
                    <li>✓ Quality certified</li>
                </ul>
                <a href="#contact" class="prod-cta">Get Quote →</a>
            </div>"""

        industries = ["Manufacturing","Agriculture","Pharmaceuticals","Construction","Automotive","Food Processing","Textile","Infrastructure"]
        ind_html = "".join(f'<div class="ind-chip"><span>{x}</span></div>' for x in industries)

        testimonials = [
            ("Rajesh Kumar",  "Kumar Industries, Delhi",     "Exceptional quality and on-time delivery. Best supplier we have worked with in 5 years."),
            ("Priya Sharma",  "Sharma Enterprises, Mumbai",  "Consistent product quality, competitive pricing and responsive support team."),
            ("Amit Patel",    "Patel Manufacturing, Surat",  "We scaled our procurement 3x after partnering with them. Highly recommended."),
        ]
        testi_html = ""
        for name, comp, text in testimonials:
            testi_html += f"""
            <div class="testi-card">
                <div class="stars">★★★★★</div>
                <p>"{text}"</p>
                <div class="testi-author">
                    <div class="testi-av">{name[0]}</div>
                    <div><strong>{name}</strong><span>{comp}</span></div>
                </div>
            </div>"""

        milestones = [
            (year,      "Company Founded",        "Started operations with a vision to deliver quality"),
            (str(int(year)+3), "ISO Certification", "Achieved international quality standards"),
            (str(int(year)+6), "500+ Clients",      "Reached 500 satisfied clients across India"),
            ("Today",   "PAN India Presence",      "Serving clients in 25+ states nationwide"),
        ]
        timeline_html = ""
        for y, title, desc_t in milestones:
            timeline_html += f"""
            <div class="timeline-item">
                <div class="timeline-year">{y}</div>
                <div class="timeline-content"><h4>{title}</h4><p>{desc_t}</p></div>
            </div>"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{company} | {category} in {city} | Quality Manufacturer</title>
<meta name="description" content="{company} is a leading {category.lower()} based in {city}, India. Premium quality products, bulk orders, PAN India delivery. Contact us for quotes.">
<meta name="keywords" content="{company}, {category}, {city}, manufacturer, supplier, bulk, India">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Lora:ital,wght@0,600;1,500&display=swap" rel="stylesheet">
<style>
:root{{
  --primary:#0d2137;--secondary:#1a4570;--accent:#e8a020;
  --accent2:#f0c060;--light:#f5f7fa;--white:#fff;
  --gray:#64748b;--border:#e2e8f0;--success:#16a34a;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
html{{scroll-behavior:smooth}}
body{{font-family:'Outfit',sans-serif;color:var(--primary);background:var(--white)}}
a{{text-decoration:none}}
img{{max-width:100%}}

/* ── PREVIEW BANNER ── */
.preview-banner{{
  position:fixed;top:0;left:0;right:0;z-index:9999;
  background:linear-gradient(90deg,#7c3aed,#4f46e5);
  color:#fff;text-align:center;padding:11px 20px;
  font-size:0.82rem;font-weight:500;
  display:flex;align-items:center;justify-content:center;gap:16px;
}}
.preview-banner strong{{color:#fbbf24}}
.preview-banner a{{
  background:#fbbf24;color:#1e1b4b;padding:5px 14px;
  border-radius:20px;font-weight:700;font-size:0.78rem;
}}

/* ── NAV ── */
nav{{
  position:fixed;top:44px;width:100%;z-index:100;
  background:rgba(13,33,55,0.97);backdrop-filter:blur(16px);
  height:68px;display:flex;align-items:center;
  justify-content:space-between;padding:0 6%;
  border-bottom:1px solid rgba(232,160,32,0.15);
  transition:top 0.3s;
}}
.nav-logo{{display:flex;align-items:center;gap:12px}}
.logo-mark{{
  width:42px;height:42px;background:var(--accent);border-radius:10px;
  display:flex;align-items:center;justify-content:center;
  font-family:'Lora',serif;font-size:1.3rem;color:var(--primary);font-weight:700;
}}
.nav-brand{{color:#fff;font-weight:700;font-size:1rem;line-height:1.2}}
.nav-brand small{{display:block;font-size:0.7rem;color:rgba(255,255,255,0.45);font-weight:400}}
.nav-links{{display:flex;gap:28px;list-style:none}}
.nav-links a{{color:rgba(255,255,255,0.7);font-size:0.88rem;font-weight:500;transition:color 0.2s}}
.nav-links a:hover{{color:var(--accent)}}
.nav-cta{{
  background:var(--accent);color:var(--primary);padding:9px 22px;
  border-radius:8px;font-weight:700;font-size:0.85rem;
  transition:all 0.2s;white-space:nowrap;
}}
.nav-cta:hover{{background:var(--accent2);transform:translateY(-1px)}}

/* ── HERO ── */
.hero{{
  min-height:100vh;padding:160px 6% 80px;
  background:linear-gradient(135deg,rgba(13,33,55,0.95) 0%,rgba(26,69,112,0.9) 100%),
             url('{hero_img}') center/cover no-repeat;
  display:flex;align-items:center;position:relative;overflow:hidden;
}}
.hero::after{{
  content:'';position:absolute;bottom:0;left:0;right:0;height:100px;
  background:linear-gradient(transparent,var(--white));
}}
.hero-content{{position:relative;z-index:1;max-width:680px}}
.hero-tag{{
  display:inline-flex;align-items:center;gap:8px;
  background:rgba(232,160,32,0.15);border:1px solid rgba(232,160,32,0.4);
  color:var(--accent);padding:7px 18px;border-radius:99px;
  font-size:0.78rem;font-weight:700;letter-spacing:0.06em;
  text-transform:uppercase;margin-bottom:24px;
}}
.hero h1{{
  font-family:'Lora',serif;
  font-size:clamp(2.4rem,5vw,3.8rem);
  color:#fff;line-height:1.15;margin-bottom:20px;
}}
.hero h1 em{{color:var(--accent);font-style:normal}}
.hero p{{
  color:rgba(255,255,255,0.72);font-size:1.08rem;
  line-height:1.75;margin-bottom:38px;max-width:560px;
}}
.hero-btns{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:52px}}
.btn-gold{{
  background:var(--accent);color:var(--primary);
  padding:15px 34px;border-radius:10px;font-weight:700;
  font-size:0.95rem;transition:all 0.25s;
  display:inline-flex;align-items:center;gap:8px;
}}
.btn-gold:hover{{background:var(--accent2);transform:translateY(-2px);box-shadow:0 8px 28px rgba(232,160,32,0.4)}}
.btn-ghost-white{{
  border:1.5px solid rgba(255,255,255,0.35);color:#fff;
  padding:15px 34px;border-radius:10px;font-weight:500;
  font-size:0.95rem;transition:all 0.25s;
  display:inline-flex;align-items:center;gap:8px;
}}
.btn-ghost-white:hover{{border-color:var(--accent);color:var(--accent)}}
.hero-stats{{
  display:flex;gap:0;
  background:rgba(255,255,255,0.06);
  border:1px solid rgba(255,255,255,0.12);
  border-radius:14px;overflow:hidden;width:fit-content;
}}
.stat{{padding:20px 32px;text-align:center;border-right:1px solid rgba(255,255,255,0.1)}}
.stat:last-child{{border-right:none}}
.stat-n{{font-family:'Lora',serif;font-size:2rem;color:var(--accent);font-weight:700}}
.stat-l{{color:rgba(255,255,255,0.5);font-size:0.75rem;margin-top:2px}}

/* ── SHARED SECTION STYLES ── */
.section{{padding:96px 6%}}
.section.bg-light{{background:var(--light)}}
.section.bg-dark{{background:var(--primary)}}
.section-eyebrow{{
  display:inline-block;background:rgba(232,160,32,0.12);
  color:var(--accent);padding:5px 16px;border-radius:99px;
  font-size:0.72rem;font-weight:800;letter-spacing:0.09em;
  text-transform:uppercase;margin-bottom:12px;
}}
.section-title{{
  font-family:'Lora',serif;
  font-size:clamp(1.9rem,3.5vw,2.7rem);
  line-height:1.2;margin-bottom:14px;
}}
.section.bg-dark .section-title{{color:#fff}}
.section-sub{{color:var(--gray);font-size:1rem;line-height:1.7;max-width:580px;margin-bottom:52px}}
.section.bg-dark .section-sub{{color:rgba(255,255,255,0.5)}}

/* ── ABOUT ── */
.about-grid{{display:grid;grid-template-columns:1fr 1fr;gap:64px;align-items:center}}
.about-features{{display:grid;gap:14px;margin-top:28px}}
.feat{{
  display:flex;gap:14px;align-items:flex-start;
  background:var(--white);padding:18px 20px;border-radius:12px;
  border:1px solid var(--border);transition:all 0.2s;
}}
.feat:hover{{border-color:var(--accent);transform:translateX(4px)}}
.feat-icon{{
  width:44px;height:44px;background:rgba(232,160,32,0.1);
  border-radius:10px;display:flex;align-items:center;
  justify-content:center;font-size:1.2rem;flex-shrink:0;
}}
.feat h4{{font-weight:700;font-size:0.92rem;margin-bottom:3px}}
.feat p{{color:var(--gray);font-size:0.82rem;line-height:1.5}}
.about-visual{{
  background:linear-gradient(150deg,var(--primary),var(--secondary));
  border-radius:20px;padding:48px 36px;text-align:center;color:#fff;
  position:relative;overflow:hidden;
}}
.about-visual::before{{
  content:'';position:absolute;top:-40px;right:-40px;
  width:200px;height:200px;border-radius:50%;
  background:rgba(232,160,32,0.07);
}}
.big-logo{{
  width:90px;height:90px;background:var(--accent);border-radius:20px;
  display:flex;align-items:center;justify-content:center;
  font-family:'Lora',serif;font-size:2.8rem;color:var(--primary);
  font-weight:700;margin:0 auto 20px;
}}
.about-visual h3{{font-family:'Lora',serif;font-size:1.5rem;margin-bottom:6px}}
.about-visual p{{color:rgba(255,255,255,0.55);font-size:0.88rem;margin-bottom:20px}}
.badges{{display:flex;gap:8px;justify-content:center;flex-wrap:wrap}}
.badge{{
  background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.15);
  padding:5px 14px;border-radius:99px;font-size:0.75rem;color:rgba(255,255,255,0.8);
}}

/* ── TIMELINE ── */
.timeline{{display:grid;gap:0;margin-top:24px;position:relative}}
.timeline::before{{
  content:'';position:absolute;left:80px;top:0;bottom:0;
  width:2px;background:var(--border);
}}
.timeline-item{{display:flex;gap:24px;padding:20px 0;position:relative}}
.timeline-year{{
  min-width:70px;font-weight:800;color:var(--accent);font-size:0.9rem;
  padding-top:4px;text-align:right;
}}
.timeline-content{{
  background:var(--white);border:1px solid var(--border);
  border-radius:10px;padding:16px 20px;flex:1;margin-left:16px;
}}
.timeline-content h4{{font-weight:700;margin-bottom:4px;font-size:0.92rem}}
.timeline-content p{{color:var(--gray);font-size:0.82rem}}

/* ── PRODUCTS ── */
.prod-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:24px}}
.prod-card{{
  border:1px solid var(--border);border-radius:14px;padding:30px 24px;
  background:var(--white);transition:all 0.25s;position:relative;overflow:hidden;
}}
.prod-card::after{{
  content:'';position:absolute;top:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,var(--accent),transparent);
  transform:scaleX(0);transform-origin:left;transition:transform 0.3s;
}}
.prod-card:hover{{transform:translateY(-5px);box-shadow:0 20px 48px rgba(13,33,55,0.1);border-color:var(--accent)}}
.prod-card:hover::after{{transform:scaleX(1)}}
.prod-icon{{font-size:2.2rem;margin-bottom:16px}}
.prod-card h3{{font-weight:700;font-size:1rem;margin-bottom:10px}}
.prod-card p{{color:var(--gray);font-size:0.83rem;line-height:1.6;margin-bottom:14px}}
.prod-specs{{list-style:none;margin-bottom:18px}}
.prod-specs li{{font-size:0.8rem;color:var(--success);padding:2px 0;font-weight:500}}
.prod-cta{{color:var(--accent);font-weight:700;font-size:0.85rem}}
.prod-cta:hover{{text-decoration:underline}}

/* ── INDUSTRIES ── */
.ind-grid{{display:flex;flex-wrap:wrap;gap:12px;margin-top:16px}}
.ind-chip{{
  background:var(--white);border:1.5px solid var(--border);
  border-radius:10px;padding:14px 20px;font-weight:600;font-size:0.88rem;
  display:flex;align-items:center;gap:10px;transition:all 0.2s;cursor:default;
}}
.ind-chip:hover{{border-color:var(--accent);background:rgba(232,160,32,0.05);transform:translateY(-2px)}}

/* ── WHY US ── */
.why-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:24px}}
.why-card{{
  background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);
  border-radius:14px;padding:30px 24px;text-align:center;transition:all 0.25s;
}}
.why-card:hover{{background:rgba(232,160,32,0.08);border-color:rgba(232,160,32,0.3)}}
.why-icon{{font-size:2.5rem;margin-bottom:16px}}
.why-card h3{{color:#fff;font-weight:700;font-size:1rem;margin-bottom:10px}}
.why-card p{{color:rgba(255,255,255,0.55);font-size:0.83rem;line-height:1.6}}

/* ── TESTIMONIALS ── */
.testi-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:24px}}
.testi-card{{
  background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);
  border-radius:14px;padding:28px 24px;
}}
.stars{{color:var(--accent);font-size:1rem;letter-spacing:3px;margin-bottom:14px}}
.testi-card p{{color:rgba(255,255,255,0.75);font-size:0.88rem;line-height:1.7;margin-bottom:20px;font-style:italic}}
.testi-author{{display:flex;align-items:center;gap:12px}}
.testi-av{{
  width:42px;height:42px;background:var(--accent);border-radius:50%;
  display:flex;align-items:center;justify-content:center;
  font-weight:800;color:var(--primary);font-size:1rem;
}}
.testi-author strong{{color:#fff;font-size:0.88rem;display:block}}
.testi-author span{{color:rgba(255,255,255,0.4);font-size:0.75rem}}

/* ── CTA BANNER ── */
.cta-banner{{
  background:linear-gradient(135deg,var(--accent) 0%,var(--accent2) 100%);
  padding:72px 6%;text-align:center;
}}
.cta-banner h2{{font-family:'Lora',serif;font-size:clamp(1.8rem,3.5vw,2.6rem);color:var(--primary);margin-bottom:14px}}
.cta-banner p{{color:rgba(13,33,55,0.7);font-size:1rem;margin-bottom:32px;max-width:520px;margin-inline:auto}}
.btn-dark{{
  background:var(--primary);color:#fff;padding:15px 36px;
  border-radius:10px;font-weight:700;font-size:0.95rem;
  display:inline-flex;align-items:center;gap:8px;transition:all 0.2s;
}}
.btn-dark:hover{{transform:translateY(-2px);box-shadow:0 8px 28px rgba(13,33,55,0.3)}}

/* ── CONTACT ── */
.contact-grid{{display:grid;grid-template-columns:1fr 1.2fr;gap:56px;align-items:start}}
.contact-info{{display:grid;gap:16px}}
.c-item{{
  display:flex;gap:16px;align-items:flex-start;
  background:var(--light);padding:20px;border-radius:12px;
  border:1px solid var(--border);
}}
.c-icon{{
  width:46px;height:46px;background:var(--primary);border-radius:10px;
  display:flex;align-items:center;justify-content:center;
  font-size:1.1rem;flex-shrink:0;
}}
.c-item h4{{font-weight:700;font-size:0.88rem;margin-bottom:4px}}
.c-item p,.c-item a{{color:var(--gray);font-size:0.85rem}}
.c-item a{{color:var(--secondary);font-weight:600}}
.map-wrap{{border-radius:12px;overflow:hidden;height:180px;margin-top:16px;border:1px solid var(--border)}}
.map-wrap iframe{{width:100%;height:100%;border:none}}
.contact-form{{background:var(--light);border-radius:16px;padding:38px;border:1px solid var(--border)}}
.form-title{{font-family:'Lora',serif;font-size:1.5rem;margin-bottom:24px}}
.fg{{margin-bottom:16px}}
.fg label{{display:block;font-size:0.8rem;font-weight:700;color:var(--primary);margin-bottom:6px;letter-spacing:0.02em}}
.fg input,.fg textarea,.fg select{{
  width:100%;padding:12px 15px;border:1.5px solid var(--border);
  border-radius:9px;font-family:'Outfit',sans-serif;font-size:0.9rem;
  color:var(--primary);background:var(--white);outline:none;
  transition:border-color 0.2s;
}}
.fg input:focus,.fg textarea:focus,.fg select:focus{{border-color:var(--accent)}}
.fg textarea{{height:110px;resize:none}}
.fg-row{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
.submit{{
  width:100%;background:var(--primary);color:#fff;
  padding:14px;border:none;border-radius:9px;font-size:0.95rem;
  font-weight:700;cursor:pointer;transition:all 0.2s;
  font-family:'Outfit',sans-serif;letter-spacing:0.02em;
}}
.submit:hover{{background:var(--accent);color:var(--primary)}}

/* ── QUALITY SECTION ── */
.quality-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:20px}}
.q-card{{
  background:var(--white);border:1px solid var(--border);
  border-radius:12px;padding:24px 20px;text-align:center;
}}
.q-num{{font-family:'Lora',serif;font-size:2.2rem;color:var(--accent);font-weight:700}}
.q-label{{color:var(--gray);font-size:0.82rem;margin-top:4px}}

/* ── FOOTER ── */
.footer{{background:var(--primary);padding:48px 6% 28px}}
.footer-grid{{display:grid;grid-template-columns:2fr 1fr 1fr;gap:48px;margin-bottom:36px}}
.footer-brand .logo-mark{{margin-bottom:14px}}
.footer-brand p{{color:rgba(255,255,255,0.45);font-size:0.85rem;line-height:1.7;max-width:280px}}
.footer h4{{color:#fff;font-weight:700;font-size:0.9rem;margin-bottom:16px}}
.footer ul{{list-style:none}}
.footer ul li{{margin-bottom:9px}}
.footer ul li a{{color:rgba(255,255,255,0.45);font-size:0.83rem;transition:color 0.2s}}
.footer ul li a:hover{{color:var(--accent)}}
.footer-bottom{{
  border-top:1px solid rgba(255,255,255,0.08);
  padding-top:24px;display:flex;
  justify-content:space-between;align-items:center;
  color:rgba(255,255,255,0.3);font-size:0.78rem;
}}
.footer-bottom a{{color:var(--accent);font-weight:600}}

/* ── WHATSAPP ── */
.wa-btn{{
  position:fixed;bottom:28px;right:28px;z-index:998;
  background:#25d366;color:#fff;width:60px;height:60px;
  border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:1.7rem;box-shadow:0 6px 24px rgba(37,211,102,0.45);
  transition:all 0.2s;
}}
.wa-btn:hover{{transform:scale(1.12)}}
.wa-tooltip{{
  position:fixed;bottom:43px;right:98px;z-index:997;
  background:var(--primary);color:#fff;padding:8px 16px;
  border-radius:8px;font-size:0.8rem;font-weight:500;
  white-space:nowrap;box-shadow:0 4px 14px rgba(0,0,0,0.15);
  pointer-events:none;
}}
.wa-tooltip::after{{
  content:'';position:absolute;right:-6px;top:50%;transform:translateY(-50%);
  border:6px solid transparent;border-left-color:var(--primary);border-right:none;
}}

/* ── RESPONSIVE ── */
@media(max-width:900px){{
  .about-grid,.contact-grid,.why-grid{{grid-template-columns:1fr}}
  .quality-grid{{grid-template-columns:repeat(2,1fr)}}
  .footer-grid{{grid-template-columns:1fr}}
  .nav-links{{display:none}}
  .hero h1{{font-size:2.2rem}}
}}
</style>
</head>
<body>

<!-- Preview Banner -->
<div class="preview-banner">
  🎨 <strong>Free Sample Website</strong> created for {company} by DigitalBoost Agency &nbsp;·&nbsp;
  <a href="#contact">Claim Your Real Website →</a>
</div>

<!-- Nav -->
<nav id="navbar">
  <div class="nav-logo">
    <div class="logo-mark">{letter}</div>
    <div class="nav-brand">{company}<small>{category} · {city}</small></div>
  </div>
  <ul class="nav-links">
    <li><a href="#about">About</a></li>
    <li><a href="#products">Products</a></li>
    <li><a href="#why-us">Why Us</a></li>
    <li><a href="#quality">Quality</a></li>
    <li><a href="#contact">Contact</a></li>
  </ul>
  <a href="{wa_link}" class="nav-cta">📱 Get Quote</a>
</nav>

<!-- HERO -->
<section class="hero">
  <div class="hero-content">
    <div class="hero-tag">⚡ Trusted Manufacturer · {city}, India</div>
    <h1>Premium <em>{category}</em><br>You Can Rely On</h1>
    <p>{desc[:160]}... Serving 500+ satisfied clients across India with consistent quality and on-time delivery.</p>
    <div class="hero-btns">
      <a href="#products" class="btn-gold">🏭 View Products</a>
      <a href="{wa_link}" class="btn-ghost-white">💬 WhatsApp Now</a>
    </div>
    <div class="hero-stats">
      <div class="stat"><div class="stat-n">500+</div><div class="stat-l">Happy Clients</div></div>
      <div class="stat"><div class="stat-n">{len(products)}+</div><div class="stat-l">Products</div></div>
      <div class="stat"><div class="stat-n">25+</div><div class="stat-l">States Served</div></div>
      <div class="stat"><div class="stat-n">Est.{year}</div><div class="stat-l">Years of Trust</div></div>
    </div>
  </div>
</section>

<!-- ABOUT -->
<section class="section bg-light" id="about">
  <div class="about-grid">
    <div>
      <div class="section-eyebrow">About Us</div>
      <h2 class="section-title">Built on Trust.<br>Driven by Quality.</h2>
      <p style="color:var(--gray);line-height:1.75;margin-bottom:28px">{desc}</p>
      <div class="about-features">
        <div class="feat"><div class="feat-icon">🏆</div><div><h4>Industry Expertise</h4><p>Years of deep domain knowledge in {category.lower()}</p></div></div>
        <div class="feat"><div class="feat-icon">🚚</div><div><h4>PAN India Delivery</h4><p>Fast, reliable logistics to all 28 states</p></div></div>
        <div class="feat"><div class="feat-icon">🤝</div><div><h4>Bulk Order Specialists</h4><p>Custom pricing and terms for large volume</p></div></div>
        <div class="feat"><div class="feat-icon">📋</div><div><h4>Full Compliance</h4><p>ISO certified, GST registered, quality assured</p></div></div>
      </div>
    </div>
    <div class="about-visual">
      <div class="big-logo">{letter}</div>
      <h3>{company}</h3>
      <p>{city}, India · Est. {year}</p>
      <div class="badges">
        <span class="badge">✓ GST Verified</span>
        <span class="badge">✓ ISO Compliant</span>
        <span class="badge">✓ PAN India</span>
        <span class="badge">✓ Bulk Ready</span>
      </div>
      <div class="timeline" style="margin-top:28px;text-align:left">
        {timeline_html}
      </div>
    </div>
  </div>
</section>

<!-- PRODUCTS -->
<section class="section" id="products">
  <div class="section-eyebrow">Our Products</div>
  <h2 class="section-title">What We Manufacture</h2>
  <p class="section-sub">High-quality products manufactured to IS/ISO standards. All products available for bulk orders with custom specifications.</p>
  <div class="prod-grid">{products_cards}</div>
</section>

<!-- INDUSTRIES -->
<section class="section bg-light" id="industries">
  <div class="section-eyebrow">Industries Served</div>
  <h2 class="section-title">Who We Supply To</h2>
  <p class="section-sub">Our products are trusted across a wide range of industries throughout India.</p>
  <div class="ind-grid">{ind_html}</div>
</section>

<!-- QUALITY -->
<section class="section" id="quality">
  <div class="section-eyebrow">Quality Assurance</div>
  <h2 class="section-title">Our Quality Promise</h2>
  <p class="section-sub">Every product goes through strict quality control before dispatch. We maintain international standards for all our manufacturing processes.</p>
  <div class="quality-grid">
    <div class="q-card"><div class="q-num">100%</div><div class="q-label">Quality Tested</div></div>
    <div class="q-card"><div class="q-num">ISO</div><div class="q-label">Certified Process</div></div>
    <div class="q-card"><div class="q-num">500+</div><div class="q-label">Happy Clients</div></div>
    <div class="q-card"><div class="q-num">24hr</div><div class="q-label">Response Time</div></div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-top:28px">
    <div class="feat"><div class="feat-icon">🔬</div><div><h4>Lab Testing</h4><p>Every batch tested before dispatch</p></div></div>
    <div class="feat"><div class="feat-icon">📄</div><div><h4>Certificates</h4><p>CoA and MSDS available for all products</p></div></div>
    <div class="feat"><div class="feat-icon">♻️</div><div><h4>Sustainable</h4><p>Eco-friendly manufacturing practices</p></div></div>
  </div>
</section>

<!-- WHY US -->
<section class="section bg-dark" id="why-us">
  <div class="section-eyebrow">Why Choose Us</div>
  <h2 class="section-title">The {company} Advantage</h2>
  <p class="section-sub">Here's why 500+ businesses across India trust us as their preferred supplier.</p>
  <div class="why-grid">
    <div class="why-card"><div class="why-icon">⚡</div><h3>Fast Turnaround</h3><p>Quick order processing with dispatch within 24–48 hours of confirmation</p></div>
    <div class="why-card"><div class="why-icon">💰</div><h3>Competitive Pricing</h3><p>Factory-direct pricing with bulk discounts and flexible payment terms</p></div>
    <div class="why-card"><div class="why-icon">🎯</div><h3>Custom Specs</h3><p>Products manufactured to your exact specifications and requirements</p></div>
    <div class="why-card"><div class="why-icon">🏆</div><h3>Proven Quality</h3><p>ISO-compliant processes with certificates available for every batch</p></div>
    <div class="why-card"><div class="why-icon">🚚</div><h3>PAN India Delivery</h3><p>Reliable logistics network covering all major cities and tier-2 towns</p></div>
    <div class="why-card"><div class="why-icon">📞</div><h3>Dedicated Support</h3><p>Single point of contact for orders, queries and after-sales support</p></div>
  </div>
</section>

<!-- TESTIMONIALS -->
<section class="section bg-dark" id="testimonials" style="padding-top:0">
  <div class="section-eyebrow">Client Reviews</div>
  <h2 class="section-title">What Our Clients Say</h2>
  <p class="section-sub">Trusted by businesses of all sizes across India.</p>
  <div class="testi-grid">{testi_html}</div>
</section>

<!-- CTA BANNER -->
<div class="cta-banner">
  <h2>Ready to Place Your Order?</h2>
  <p>Get in touch today for a custom quote, product specifications or bulk pricing.</p>
  <a href="#contact" class="btn-dark">📩 Request a Quote Now</a>
</div>

<!-- CONTACT -->
<section class="section" id="contact">
  <div class="section-eyebrow">Contact Us</div>
  <h2 class="section-title">Get In Touch</h2>
  <p class="section-sub">Fill the form below or WhatsApp us directly for fastest response. We reply within 2 hours.</p>
  <div class="contact-grid">
    <div class="contact-info">
      <div class="c-item"><div class="c-icon">📍</div><div><h4>Our Location</h4><p>{city}, India</p></div></div>
      <div class="c-item"><div class="c-icon">📱</div><div><h4>Phone / WhatsApp</h4><p><a href="{wa_link}">{phone_d}</a></p></div></div>
      <div class="c-item"><div class="c-icon">📧</div><div><h4>Email</h4><p><a href="mailto:{email}">{email}</a></p></div></div>
      <div class="c-item"><div class="c-icon">🕒</div><div><h4>Business Hours</h4><p>Mon–Sat: 9:00 AM – 6:30 PM IST</p></div></div>
      <div class="map-wrap">
        <iframe src="https://maps.google.com/maps?q={maps_q}&output=embed" allowfullscreen loading="lazy"></iframe>
      </div>
    </div>
    <div class="contact-form">
      <h3 class="form-title">Send an Enquiry</h3>
      <div class="fg-row">
        <div class="fg"><label>Your Name *</label><input type="text" placeholder="Rajesh Kumar"></div>
        <div class="fg"><label>Company Name</label><input type="text" placeholder="Kumar Industries"></div>
      </div>
      <div class="fg-row">
        <div class="fg"><label>Phone / WhatsApp *</label><input type="tel" placeholder="+91 98765 43210"></div>
        <div class="fg"><label>Email Address</label><input type="email" placeholder="rajesh@company.com"></div>
      </div>
      <div class="fg">
        <label>Product Required *</label>
        <select>
          <option value="">Select a product...</option>
          {"".join(f'<option>{p}</option>' for p in products)}
          <option>Other / Custom Requirement</option>
        </select>
      </div>
      <div class="fg"><label>Quantity Required</label><input type="text" placeholder="e.g. 500 kg, 100 units, 1 tonne"></div>
      <div class="fg"><label>Message / Specifications</label><textarea placeholder="Please describe your requirement, delivery location, timeline..."></textarea></div>
      <button class="submit" onclick="handleSubmit(this)">Send Enquiry →</button>
    </div>
  </div>
</section>

<!-- FOOTER -->
<footer class="footer">
  <div class="footer-grid">
    <div class="footer-brand">
      <div class="logo-mark">{letter}</div>
      <p style="margin-top:12px">{desc[:120]}...</p>
      <div style="margin-top:16px;display:flex;gap:10px">
        <a href="{wa_link}" style="background:#25d366;color:#fff;padding:8px 16px;border-radius:8px;font-size:0.8rem;font-weight:600">💬 WhatsApp</a>
        <a href="tel:+91{phone}" style="background:var(--secondary);color:#fff;padding:8px 16px;border-radius:8px;font-size:0.8rem;font-weight:600">📞 Call Us</a>
      </div>
    </div>
    <div>
      <h4>Quick Links</h4>
      <ul>
        <li><a href="#about">About Us</a></li>
        <li><a href="#products">Products</a></li>
        <li><a href="#why-us">Why Choose Us</a></li>
        <li><a href="#quality">Quality</a></li>
        <li><a href="#contact">Contact</a></li>
      </ul>
    </div>
    <div>
      <h4>Products</h4>
      <ul>{"".join(f'<li><a href="#products">{p}</a></li>' for p in products[:5])}</ul>
    </div>
  </div>
  <div class="footer-bottom">
    <span>© 2024 <strong style="color:rgba(255,255,255,0.7)">{company}</strong> · {city}, India</span>
    <span>Website by <a href="#contact">DigitalBoost Agency</a></span>
  </div>
</footer>

<!-- WhatsApp Float -->
<a href="{wa_link}" class="wa-btn" target="_blank">💬</a>
<div class="wa-tooltip">Chat on WhatsApp</div>

<script>
// Sticky nav shift after banner
window.addEventListener('scroll', () => {{
  const nav = document.getElementById('navbar');
  if(window.scrollY > 60) {{
    nav.style.top = '0';
    nav.style.boxShadow = '0 4px 24px rgba(0,0,0,0.3)';
  }} else {{
    nav.style.top = '44px';
    nav.style.boxShadow = 'none';
  }}
}});

// Smooth scroll
document.querySelectorAll('a[href^="#"]').forEach(a => {{
  a.addEventListener('click', e => {{
    const el = document.querySelector(a.getAttribute('href'));
    if(el) {{ e.preventDefault(); el.scrollIntoView({{behavior:'smooth'}}); }}
  }});
}});

// Form submit
function handleSubmit(btn) {{
  btn.textContent = '✓ Enquiry Sent!';
  btn.style.background = '#16a34a';
  btn.disabled = true;
  setTimeout(() => {{
    btn.textContent = 'Send Enquiry →';
    btn.style.background = '';
    btn.disabled = false;
  }}, 4000);
}}

// Fade in on scroll
const io = new IntersectionObserver(entries => {{
  entries.forEach(e => {{
    if(e.isIntersecting) {{
      e.target.style.opacity = '1';
      e.target.style.transform = 'translateY(0)';
    }}
  }});
}}, {{threshold:0.1}});
document.querySelectorAll('.prod-card,.why-card,.testi-card,.feat,.q-card').forEach(el => {{
  el.style.opacity = '0';
  el.style.transform = 'translateY(20px)';
  el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
  io.observe(el);
}});
</script>
</body>
</html>"""


def generate_preview_for_lead(lead):
    """Main entry point — generate full website for a lead."""
    company   = lead.get("company") or lead.get("name") or "Company"
    city      = lead.get("city") or "India"
    indiamart = lead.get("indiamart_url") or lead.get("website") or ""
    products  = lead.get("products") or ""
    category  = lead.get("category") or "Chemicals"

    print("[Preview] Generating for: " + company)

    scraper = IndiaMArtScraper()
    data    = scraper.scrape(indiamart, company, city, products, category)

    if not data["phone"] and lead.get("phone"):
        data["phone"] = str(lead["phone"])
    if not data["email"] and lead.get("email"):
        data["email"] = str(lead["email"])

    slug = slugify(company)
    gen  = WebsiteGenerator()
    html = gen.generate(data, slug)

    preview_url = BASE_URL + "/preview/" + slug
    GENERATED_SITES[slug] = {
        "html": html, "company": company,
        "slug": slug, "lead_id": lead.get("id"),
        "preview_url": preview_url,
        "created_at": datetime.utcnow().isoformat(),
    }

    # Save preview URL to DB (using linkedin_url column as preview_url)
    try:
        from database import get_conn
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(
            "UPDATE leads SET linkedin_url=%s, updated_at=%s WHERE id=%s",
            (preview_url, datetime.utcnow().isoformat(), lead.get("id"))
        )
        conn.commit()
        cur.close()
        conn.close()
        print("[Preview] Saved: " + preview_url)
    except Exception as e:
        print("[Preview] DB error: " + str(e))

    return GENERATED_SITES[slug]
