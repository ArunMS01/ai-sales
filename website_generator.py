"""
WEBSITE GENERATOR
==================
Scrapes IndiaMART seller data and generates a beautiful
modern preview website hosted on Railway.

Access at: /preview/{company-slug}
"""
import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime

SERPAPI_KEY  = os.getenv("SERPAPI_KEY", "")
OPENAI_KEY   = os.getenv("OPENAI_API_KEY", "")
BASE_URL     = os.getenv("WEBHOOK_BASE_URL", "https://web-production-6a55a.up.railway.app")

# In-memory store of generated websites {slug: html}
GENERATED_SITES = {}


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text[:40]


class IndiaMArtScraper:
    """Scrapes real data from IndiaMART seller profile."""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html",
    }

    def scrape(self, indiamart_url, company_name, city, products_hint=""):
        data = {
            "company":     company_name,
            "city":        city,
            "products":    [],
            "description": "",
            "phone":       "",
            "email":       "",
            "year":        "",
            "logo_letter": company_name[0].upper() if company_name else "C",
            "category":    "Chemical Manufacturer",
        }

        if not indiamart_url or "indiamart" not in indiamart_url:
            data["products"] = self._default_products(products_hint)
            return data

        try:
            resp = requests.get(indiamart_url, headers=self.HEADERS, timeout=12)
            if resp.status_code != 200:
                data["products"] = self._default_products(products_hint)
                return data

            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text(" ", strip=True)

            # Products — find listed items
            product_els = (
                soup.find_all("div", class_=re.compile(r"product|item|catalog", re.I)) or
                soup.find_all("li",  class_=re.compile(r"product|item", re.I))
            )
            for el in product_els[:12]:
                name = el.get_text(strip=True)[:60]
                if name and len(name) > 3 and name not in data["products"]:
                    data["products"].append(name)

            # Description / about
            desc_el = soup.find(class_=re.compile(r"about|description|overview|profile", re.I))
            if desc_el:
                data["description"] = desc_el.get_text(" ", strip=True)[:300]

            # Phone
            phones = re.findall(r'[6-9]\d{9}', text)
            skip   = ["9696969696", "8888888888"]
            for p in phones:
                if p not in skip:
                    data["phone"] = p
                    break

            # Email
            emails = re.findall(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', text)
            for e in emails:
                if "indiamart" not in e and len(e) < 60:
                    data["email"] = e
                    break

            # Year established
            year = re.search(r'(?:established|est\.?|since|founded)[^\d]*(\d{4})', text, re.I)
            if year:
                data["year"] = year.group(1)

        except Exception as ex:
            print("[Scraper] Error: " + str(ex)[:80])

        if not data["products"]:
            data["products"] = self._default_products(products_hint)

        return data

    def _default_products(self, hint=""):
        if "chemical" in hint.lower() or not hint:
            return [
                "Industrial Chemicals", "Agricultural Chemicals",
                "Cleaning Chemicals", "Paint & Coating Chemicals",
                "Water Treatment Chemicals", "Pharmaceutical Chemicals",
                "Specialty Chemicals", "Laboratory Reagents"
            ]
        return ["Product 1", "Product 2", "Product 3", "Product 4"]


class WebsiteGenerator:
    """Generates beautiful modern HTML website from company data."""

    def generate(self, data, lead_id=None):
        company  = data.get("company", "Your Company")
        city     = data.get("city", "India")
        products = data.get("products", [])[:8]
        desc     = data.get("description", "")
        phone    = data.get("phone", "")
        email    = data.get("email", "")
        year     = data.get("year", "")
        letter   = company[0].upper() if company else "C"

        # Auto-generate description if missing
        if not desc:
            desc = (
                company + " is a leading manufacturer and supplier based in " + city +
                ", India. We specialize in high-quality " +
                (products[0] if products else "industrial products") +
                " and have been serving clients across India with excellence and reliability."
            )

        # Auto-generate testimonials
        testimonials = [
            {"name": "Rajesh Kumar",    "company": "Kumar Industries, Delhi",    "text": "Excellent quality products and timely delivery. Highly recommended!"},
            {"name": "Priya Sharma",    "company": "Sharma Enterprises, Mumbai", "text": "We have been sourcing from them for 3 years. Consistent quality every time."},
            {"name": "Amit Patel",      "company": "Patel Manufacturing, Surat", "text": "Best supplier in the region. Competitive pricing and great support."},
        ]

        products_html = ""
        for i, p in enumerate(products):
            icon = ["⚗️","🧪","🏭","🔬","💊","🌿","🧴","⚙️"][i % 8]
            products_html += f"""
            <div class="product-card">
                <div class="product-icon">{icon}</div>
                <h3>{p}</h3>
                <p>Premium quality {p.lower()} manufactured to industry standards with full compliance and quality assurance.</p>
                <a href="#contact" class="product-link">Get Quote →</a>
            </div>"""

        testimonials_html = ""
        for t in testimonials:
            testimonials_html += f"""
            <div class="testimonial-card">
                <div class="stars">★★★★★</div>
                <p>"{t['text']}"</p>
                <div class="testimonial-author">
                    <div class="author-avatar">{t['name'][0]}</div>
                    <div>
                        <strong>{t['name']}</strong>
                        <span>{t['company']}</span>
                    </div>
                </div>
            </div>"""

        wa_link   = ("https://wa.me/91" + phone) if phone else "#contact"
        maps_link = "https://maps.google.com/?q=" + requests.utils.quote(company + " " + city)
        year_text = ("Est. " + year) if year else "Trusted Manufacturer"
        phone_display = phone if phone else "+91 XXXXX XXXXX"
        email_display = email if email else "info@" + slugify(company) + ".com"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{company} | {city}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
:root {{
    --navy:   #0a1628;
    --blue:   #1a3a6e;
    --accent: #c8972a;
    --light:  #f8f6f1;
    --white:  #ffffff;
    --gray:   #64748b;
    --border: #e2d9c8;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{ font-family: 'DM Sans', sans-serif; background: var(--white); color: var(--navy); }}

/* NAV */
nav {{
    position: fixed; top: 0; width: 100%; z-index: 100;
    background: rgba(10,22,40,0.97); backdrop-filter: blur(12px);
    padding: 0 5%; display: flex; align-items: center;
    justify-content: space-between; height: 70px;
    border-bottom: 1px solid rgba(200,151,42,0.2);
}}
.nav-logo {{ display: flex; align-items: center; gap: 12px; }}
.logo-mark {{
    width: 40px; height: 40px; background: var(--accent);
    border-radius: 8px; display: flex; align-items: center;
    justify-content: center; font-family: 'Playfair Display', serif;
    font-size: 1.2rem; color: var(--navy); font-weight: 700;
}}
.nav-brand {{ color: var(--white); font-weight: 600; font-size: 1rem; }}
.nav-links {{ display: flex; gap: 32px; list-style: none; }}
.nav-links a {{ color: rgba(255,255,255,0.75); text-decoration: none; font-size: 0.9rem; font-weight: 500; transition: color 0.2s; }}
.nav-links a:hover {{ color: var(--accent); }}
.nav-cta {{
    background: var(--accent); color: var(--navy); padding: 9px 22px;
    border-radius: 6px; text-decoration: none; font-weight: 600;
    font-size: 0.85rem; transition: opacity 0.2s;
}}
.nav-cta:hover {{ opacity: 0.85; }}

/* HERO */
.hero {{
    min-height: 100vh;
    background: linear-gradient(135deg, var(--navy) 0%, var(--blue) 60%, #0f2a5a 100%);
    display: flex; align-items: center;
    padding: 100px 5% 60px;
    position: relative; overflow: hidden;
}}
.hero::before {{
    content: ''; position: absolute; inset: 0;
    background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23c8972a' fill-opacity='0.04'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
}}
.hero-content {{ position: relative; max-width: 640px; }}
.hero-badge {{
    display: inline-flex; align-items: center; gap: 8px;
    background: rgba(200,151,42,0.15); border: 1px solid rgba(200,151,42,0.3);
    color: var(--accent); padding: 6px 16px; border-radius: 20px;
    font-size: 0.8rem; font-weight: 600; letter-spacing: 0.05em;
    text-transform: uppercase; margin-bottom: 24px;
}}
.hero h1 {{
    font-family: 'Playfair Display', serif;
    font-size: clamp(2.2rem, 5vw, 3.6rem);
    color: var(--white); line-height: 1.15; margin-bottom: 20px;
}}
.hero h1 span {{ color: var(--accent); }}
.hero p {{
    color: rgba(255,255,255,0.7); font-size: 1.05rem;
    line-height: 1.7; margin-bottom: 36px; max-width: 520px;
}}
.hero-actions {{ display: flex; gap: 14px; flex-wrap: wrap; }}
.btn-primary {{
    background: var(--accent); color: var(--navy);
    padding: 14px 32px; border-radius: 8px; text-decoration: none;
    font-weight: 700; font-size: 0.95rem; transition: all 0.2s;
    display: inline-flex; align-items: center; gap: 8px;
}}
.btn-primary:hover {{ transform: translateY(-2px); box-shadow: 0 8px 24px rgba(200,151,42,0.35); }}
.btn-outline {{
    border: 1.5px solid rgba(255,255,255,0.3); color: var(--white);
    padding: 14px 32px; border-radius: 8px; text-decoration: none;
    font-weight: 500; font-size: 0.95rem; transition: all 0.2s;
    display: inline-flex; align-items: center; gap: 8px;
}}
.btn-outline:hover {{ border-color: var(--accent); color: var(--accent); }}
.hero-stats {{
    display: flex; gap: 40px; margin-top: 56px;
    padding-top: 40px; border-top: 1px solid rgba(255,255,255,0.1);
}}
.stat-item {{ text-align: left; }}
.stat-num {{ font-family: 'Playfair Display', serif; font-size: 2rem; color: var(--accent); font-weight: 700; }}
.stat-label {{ color: rgba(255,255,255,0.5); font-size: 0.8rem; margin-top: 2px; }}

/* SECTIONS */
section {{ padding: 90px 5%; }}
.section-tag {{
    display: inline-block; background: rgba(200,151,42,0.1);
    color: var(--accent); padding: 5px 14px; border-radius: 20px;
    font-size: 0.75rem; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase; margin-bottom: 14px;
}}
.section-title {{
    font-family: 'Playfair Display', serif;
    font-size: clamp(1.8rem, 3.5vw, 2.6rem);
    color: var(--navy); margin-bottom: 14px; line-height: 1.2;
}}
.section-subtitle {{ color: var(--gray); font-size: 1rem; line-height: 1.7; max-width: 560px; margin-bottom: 50px; }}

/* ABOUT */
.about {{ background: var(--light); }}
.about-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 60px; align-items: center; }}
.about-features {{ display: grid; gap: 16px; margin-top: 30px; }}
.feature-item {{
    display: flex; align-items: flex-start; gap: 14px;
    background: var(--white); padding: 18px 20px; border-radius: 10px;
    border: 1px solid var(--border);
}}
.feature-icon {{
    width: 40px; height: 40px; background: rgba(200,151,42,0.1);
    border-radius: 8px; display: flex; align-items: center;
    justify-content: center; font-size: 1.1rem; flex-shrink: 0;
}}
.feature-text h4 {{ font-weight: 600; font-size: 0.95rem; margin-bottom: 3px; }}
.feature-text p {{ color: var(--gray); font-size: 0.85rem; }}
.about-visual {{
    background: linear-gradient(135deg, var(--navy), var(--blue));
    border-radius: 16px; padding: 50px 40px; text-align: center; color: var(--white);
}}
.about-logo-big {{
    width: 100px; height: 100px; background: var(--accent);
    border-radius: 20px; display: flex; align-items: center;
    justify-content: center; font-family: 'Playfair Display', serif;
    font-size: 3rem; color: var(--navy); font-weight: 700;
    margin: 0 auto 24px;
}}
.about-visual h3 {{ font-family: 'Playfair Display', serif; font-size: 1.6rem; margin-bottom: 8px; }}
.about-visual p {{ color: rgba(255,255,255,0.65); font-size: 0.9rem; margin-bottom: 24px; }}
.trust-badges {{ display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }}
.trust-badge {{
    background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.15);
    padding: 6px 14px; border-radius: 20px; font-size: 0.78rem; color: rgba(255,255,255,0.8);
}}

/* PRODUCTS */
.products-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 24px; }}
.product-card {{
    border: 1px solid var(--border); border-radius: 12px; padding: 28px 24px;
    transition: all 0.25s; background: var(--white);
    position: relative; overflow: hidden;
}}
.product-card::before {{
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, var(--accent), transparent);
    opacity: 0; transition: opacity 0.25s;
}}
.product-card:hover {{ transform: translateY(-4px); box-shadow: 0 16px 40px rgba(10,22,40,0.1); border-color: var(--accent); }}
.product-card:hover::before {{ opacity: 1; }}
.product-icon {{ font-size: 2rem; margin-bottom: 16px; }}
.product-card h3 {{ font-size: 1rem; font-weight: 600; margin-bottom: 10px; color: var(--navy); }}
.product-card p {{ color: var(--gray); font-size: 0.85rem; line-height: 1.6; margin-bottom: 16px; }}
.product-link {{ color: var(--accent); font-weight: 600; font-size: 0.85rem; text-decoration: none; }}
.product-link:hover {{ text-decoration: underline; }}

/* TESTIMONIALS */
.testimonials {{ background: var(--navy); }}
.testimonials .section-title {{ color: var(--white); }}
.testimonials .section-subtitle {{ color: rgba(255,255,255,0.55); }}
.testimonials-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 24px; }}
.testimonial-card {{
    background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px; padding: 28px 24px;
}}
.stars {{ color: var(--accent); font-size: 1rem; margin-bottom: 14px; letter-spacing: 2px; }}
.testimonial-card p {{ color: rgba(255,255,255,0.75); font-size: 0.9rem; line-height: 1.7; margin-bottom: 20px; font-style: italic; }}
.testimonial-author {{ display: flex; align-items: center; gap: 12px; }}
.author-avatar {{
    width: 40px; height: 40px; background: var(--accent); border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; color: var(--navy); font-size: 1rem;
}}
.testimonial-author strong {{ color: var(--white); font-size: 0.9rem; display: block; }}
.testimonial-author span {{ color: rgba(255,255,255,0.45); font-size: 0.78rem; }}

/* CONTACT */
.contact-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 60px; align-items: start; }}
.contact-info {{ display: grid; gap: 20px; }}
.contact-item {{
    display: flex; gap: 16px; align-items: flex-start;
    padding: 20px; background: var(--light); border-radius: 10px;
    border: 1px solid var(--border);
}}
.contact-icon {{
    width: 44px; height: 44px; background: var(--navy); border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.1rem; flex-shrink: 0;
}}
.contact-item h4 {{ font-weight: 600; font-size: 0.9rem; margin-bottom: 4px; }}
.contact-item p {{ color: var(--gray); font-size: 0.85rem; }}
.contact-item a {{ color: var(--navy); text-decoration: none; font-weight: 500; }}
.contact-form {{ background: var(--light); border-radius: 14px; padding: 36px; border: 1px solid var(--border); }}
.contact-form h3 {{ font-family: 'Playfair Display', serif; font-size: 1.4rem; margin-bottom: 24px; }}
.form-group {{ margin-bottom: 16px; }}
.form-group label {{ display: block; font-size: 0.82rem; font-weight: 600; color: var(--navy); margin-bottom: 6px; }}
.form-group input, .form-group textarea, .form-group select {{
    width: 100%; padding: 11px 14px; border: 1.5px solid var(--border);
    border-radius: 8px; font-family: 'DM Sans', sans-serif; font-size: 0.9rem;
    color: var(--navy); background: var(--white); transition: border-color 0.2s;
    outline: none;
}}
.form-group input:focus, .form-group textarea:focus {{ border-color: var(--accent); }}
.form-group textarea {{ height: 110px; resize: none; }}
.submit-btn {{
    width: 100%; background: var(--navy); color: var(--white);
    padding: 13px; border: none; border-radius: 8px; font-size: 0.95rem;
    font-weight: 600; cursor: pointer; transition: all 0.2s;
    font-family: 'DM Sans', sans-serif;
}}
.submit-btn:hover {{ background: var(--accent); color: var(--navy); }}

/* MAP */
.map-container {{
    border-radius: 12px; overflow: hidden; border: 1px solid var(--border);
    height: 200px; margin-top: 20px;
}}
.map-container iframe {{ width: 100%; height: 100%; border: none; }}

/* WHATSAPP */
.wa-float {{
    position: fixed; bottom: 28px; right: 28px; z-index: 999;
    background: #25d366; color: white; width: 58px; height: 58px;
    border-radius: 50%; display: flex; align-items: center; justify-content: center;
    font-size: 1.6rem; text-decoration: none; box-shadow: 0 6px 24px rgba(37,211,102,0.4);
    transition: all 0.2s;
}}
.wa-float:hover {{ transform: scale(1.1); }}
.wa-label {{
    position: fixed; bottom: 42px; right: 96px; z-index: 998;
    background: var(--navy); color: var(--white); padding: 8px 16px;
    border-radius: 8px; font-size: 0.82rem; font-weight: 500;
    white-space: nowrap; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}}

/* FOOTER */
footer {{
    background: var(--navy); color: rgba(255,255,255,0.5);
    text-align: center; padding: 30px 5%; font-size: 0.82rem;
    border-top: 1px solid rgba(255,255,255,0.08);
}}
footer strong {{ color: var(--white); }}

/* PREVIEW BANNER */
.preview-banner {{
    position: fixed; top: 0; left: 0; right: 0; z-index: 9999;
    background: linear-gradient(90deg, #7c3aed, #6d28d9);
    color: white; text-align: center; padding: 10px 20px;
    font-size: 0.82rem; font-weight: 500;
}}
.preview-banner a {{ color: #fbbf24; text-decoration: none; font-weight: 700; }}
body {{ padding-top: 40px; }}

@media (max-width: 768px) {{
    .about-grid, .contact-grid {{ grid-template-columns: 1fr; }}
    .hero-stats {{ gap: 24px; flex-wrap: wrap; }}
    .nav-links {{ display: none; }}
}}
</style>
</head>
<body>

<!-- Preview Banner -->
<div class="preview-banner">
    🎨 This is a <strong>free sample website</strong> created for {company} by DigitalBoost Agency.
    <a href="#contact">Get your real website →</a>
</div>

<!-- Nav -->
<nav>
    <div class="nav-logo">
        <div class="logo-mark">{letter}</div>
        <span class="nav-brand">{company}</span>
    </div>
    <ul class="nav-links">
        <li><a href="#about">About</a></li>
        <li><a href="#products">Products</a></li>
        <li><a href="#testimonials">Reviews</a></li>
        <li><a href="#contact">Contact</a></li>
    </ul>
    <a href="{wa_link}" class="nav-cta">📱 WhatsApp Us</a>
</nav>

<!-- Hero -->
<section class="hero">
    <div class="hero-content">
        <div class="hero-badge">⚡ {year_text} · {city}, India</div>
        <h1>Leading <span>{data.get('category', 'Manufacturer')}</span><br>in {city}</h1>
        <p>{desc[:180]}...</p>
        <div class="hero-actions">
            <a href="#products" class="btn-primary">🏭 View Products</a>
            <a href="{wa_link}" class="btn-outline">💬 WhatsApp Now</a>
        </div>
        <div class="hero-stats">
            <div class="stat-item">
                <div class="stat-num">500+</div>
                <div class="stat-label">Happy Clients</div>
            </div>
            <div class="stat-item">
                <div class="stat-num">{len(products)}+</div>
                <div class="stat-label">Products</div>
            </div>
            <div class="stat-item">
                <div class="stat-num">PAN</div>
                <div class="stat-label">India Delivery</div>
            </div>
        </div>
    </div>
</section>

<!-- About -->
<section class="about" id="about">
    <div class="about-grid">
        <div>
            <div class="section-tag">About Us</div>
            <h2 class="section-title">Trusted Quality.<br>Since Day One.</h2>
            <p class="section-subtitle">{desc}</p>
            <div class="about-features">
                <div class="feature-item">
                    <div class="feature-icon">✅</div>
                    <div class="feature-text"><h4>ISO Certified Quality</h4><p>All products manufactured under strict quality control</p></div>
                </div>
                <div class="feature-item">
                    <div class="feature-icon">🚚</div>
                    <div class="feature-text"><h4>PAN India Delivery</h4><p>Fast and reliable shipping across all states</p></div>
                </div>
                <div class="feature-item">
                    <div class="feature-icon">🤝</div>
                    <div class="feature-text"><h4>Bulk Order Discounts</h4><p>Special pricing for large volume orders</p></div>
                </div>
            </div>
        </div>
        <div class="about-visual">
            <div class="about-logo-big">{letter}</div>
            <h3>{company}</h3>
            <p>{city}, India · {year_text}</p>
            <div class="trust-badges">
                <span class="trust-badge">✓ GST Verified</span>
                <span class="trust-badge">✓ ISO Compliant</span>
                <span class="trust-badge">✓ PAN India</span>
            </div>
        </div>
    </div>
</section>

<!-- Products -->
<section id="products">
    <div class="section-tag">Our Products</div>
    <h2 class="section-title">What We Manufacture</h2>
    <p class="section-subtitle">High-quality products built to industry standards, available for bulk orders across India.</p>
    <div class="products-grid">{products_html}</div>
</section>

<!-- Testimonials -->
<section class="testimonials" id="testimonials">
    <div class="section-tag">Client Reviews</div>
    <h2 class="section-title">What Our Clients Say</h2>
    <p class="section-subtitle">Trusted by 500+ businesses across India for consistent quality and service.</p>
    <div class="testimonials-grid">{testimonials_html}</div>
</section>

<!-- Contact -->
<section id="contact">
    <div class="section-tag">Get In Touch</div>
    <h2 class="section-title">Request a Quote</h2>
    <p class="section-subtitle">Fill in the form below or WhatsApp us directly for fastest response.</p>
    <div class="contact-grid">
        <div class="contact-info">
            <div class="contact-item">
                <div class="contact-icon">📍</div>
                <div><h4>Location</h4><p>{city}, India</p></div>
            </div>
            <div class="contact-item">
                <div class="contact-icon">📱</div>
                <div><h4>Phone / WhatsApp</h4><p><a href="{wa_link}">{phone_display}</a></p></div>
            </div>
            <div class="contact-item">
                <div class="contact-icon">📧</div>
                <div><h4>Email</h4><p><a href="mailto:{email_display}">{email_display}</a></p></div>
            </div>
            <div class="map-container">
                <iframe src="https://maps.google.com/maps?q={requests.utils.quote(company + ' ' + city)}&output=embed" allowfullscreen loading="lazy"></iframe>
            </div>
        </div>
        <div class="contact-form">
            <h3>Send an Enquiry</h3>
            <div class="form-group">
                <label>Your Name</label>
                <input type="text" placeholder="Rajesh Kumar">
            </div>
            <div class="form-group">
                <label>Phone / WhatsApp</label>
                <input type="tel" placeholder="+91 98765 43210">
            </div>
            <div class="form-group">
                <label>Product Required</label>
                <select>
                    <option>Select a product...</option>
                    {"".join(f'<option>{p}</option>' for p in products)}
                </select>
            </div>
            <div class="form-group">
                <label>Message</label>
                <textarea placeholder="Please share quantity, specifications, delivery location..."></textarea>
            </div>
            <button class="submit-btn" onclick="alert('Thank you! We will contact you within 24 hours.')">Send Enquiry →</button>
        </div>
    </div>
</section>

<!-- WhatsApp Float -->
<a href="{wa_link}" class="wa-float" target="_blank">💬</a>
<div class="wa-label">Chat on WhatsApp</div>

<!-- Footer -->
<footer>
    <p>© 2024 <strong>{company}</strong> · {city}, India · All rights reserved</p>
    <p style="margin-top:8px;font-size:0.75rem">Website designed by <strong>DigitalBoost Agency</strong> · Want this for your business? <a href="#contact" style="color:#c8972a">Contact us</a></p>
</footer>

<script>
// Smooth scroll
document.querySelectorAll('a[href^="#"]').forEach(a => {{
    a.addEventListener('click', e => {{
        e.preventDefault();
        document.querySelector(a.getAttribute('href'))?.scrollIntoView({{behavior:'smooth'}});
    }});
}});
// Animate on scroll
const observer = new IntersectionObserver(entries => {{
    entries.forEach(e => {{ if(e.isIntersecting) e.target.style.opacity = 1; }});
}}, {{threshold: 0.1}});
document.querySelectorAll('.product-card, .testimonial-card, .feature-item').forEach(el => {{
    el.style.opacity = '0';
    el.style.transition = 'opacity 0.5s ease';
    observer.observe(el);
}});
</script>
</body>
</html>"""
        return html


def generate_preview_for_lead(lead):
    """Main function — scrape IndiaMART data and generate website for a lead."""
    company     = lead.get("company") or lead.get("name") or "Company"
    city        = lead.get("city") or "India"
    indiamart   = lead.get("indiamart_url") or lead.get("website") or ""
    products    = lead.get("products") or ""
    category    = lead.get("category") or "Manufacturer"

    print("[Preview] Generating website for: " + company)

    # Scrape IndiaMART data
    scraper = IndiaMArtScraper()
    data    = scraper.scrape(indiamart, company, city, products)
    data["category"] = category

    # Copy phone/email from lead if scraper didn't find them
    if not data["phone"] and lead.get("phone"):
        data["phone"] = lead["phone"]
    if not data["email"] and lead.get("email"):
        data["email"] = lead["email"]

    # Generate HTML
    generator = WebsiteGenerator()
    html      = generator.generate(data, lead_id=lead.get("id"))

    # Store in memory
    slug = slugify(company)
    GENERATED_SITES[slug] = {
        "html":       html,
        "company":    company,
        "slug":       slug,
        "created_at": datetime.utcnow().isoformat(),
        "lead_id":    lead.get("id"),
        "preview_url": BASE_URL + "/preview/" + slug,
    }

    # Save preview URL back to DB
    try:
        from database import get_conn
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(
            "UPDATE leads SET linkedin_url=%s WHERE id=%s",
            (BASE_URL + "/preview/" + slug, lead.get("id"))
        )
        conn.commit()
        cur.close()
        conn.close()
        print("[Preview] URL saved to DB: /preview/" + slug)
    except Exception as e:
        print("[Preview] DB save error: " + str(e))

    return GENERATED_SITES[slug]
