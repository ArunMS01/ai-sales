import os
import json
import time
import requests
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional

# No API key needed — uses Instagram's public endpoints
# Rate limit: ~200 requests/hour per IP (Railway IP is shared, so be conservative)

INSTAGRAM_HASHTAGS = [
    "madeinindia",
    "indianbrand",
    "d2cindia",
    "indianfashion",
    "indiane commerce",
    "shopindian",
    "vocalforlocal",
    "indianstartup",
    "indiad2c",
    "indianbeauty",
    "indianwear",
    "handmadeinindia",
    "indiantextile",
    "indianjewelry",
    "indianfoodbrand",
]

# Keywords that indicate a BRAND account (not personal)
BRAND_KEYWORDS = [
    "shop", "store", "brand", "official", "collection", "wear",
    "fashion", "beauty", "skincare", "apparel", "clothing",
    "jewel", "home", "decor", "food", "organic", "natural",
    "handmade", "craft", "studio", "co.", "pvt", "ltd"
]

# Keywords that indicate it's NOT a useful lead
SKIP_KEYWORDS = [
    "photography", "photographer", "blogger", "influencer",
    "model", "artist", "musician", "actor", "coach", "trainer",
    "motivational", "spiritual", "astro", "news", "media"
]


@dataclass
class InstagramLead:
    username: str
    full_name: str
    bio: str
    website: str
    email: str
    followers: int
    following: int
    posts: int
    profile_url: str
    category: str
    city: str = "India"
    source: str = "instagram"
    stage: str = "new"
    pain_points: list = None
    company: str = ""
    job_title: str = ""
    phone: str = ""
    linkedin_url: str = ""
    seo_score: Optional[int] = None
    pagespeed_score: Optional[int] = None
    created_at: str = ""

    def __post_init__(self):
        if self.pain_points is None:
            self.pain_points = []
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
        if not self.company:
            self.company = self.full_name or self.username


class InstagramScraper:
    """
    Scrapes Instagram public data using:
    1. Hashtag search (no auth needed)
    2. Profile lookup by username (no auth needed)

    Uses Instagram's internal web API endpoints — same ones
    the browser uses when you visit instagram.com
    """

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.instagram.com/",
        "X-IG-App-ID": "936619743392459",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self._get_csrf_token()

    def _get_csrf_token(self):
        try:
            resp = self.session.get("https://www.instagram.com/", timeout=10)
            for cookie in resp.cookies:
                if cookie.name == "csrftoken":
                    self.session.headers["X-CSRFToken"] = cookie.value
                    break
        except Exception as e:
            print("[Instagram] CSRF error: " + str(e))

    def search_hashtag(self, hashtag, max_accounts=20):
        """Search a hashtag and return brand accounts."""
        url = "https://www.instagram.com/api/v1/tags/web_info/?tag_name=" + hashtag
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 429:
                print("[Instagram] Rate limited on hashtag " + hashtag + " — waiting 30s")
                time.sleep(30)
                return []
            if resp.status_code != 200:
                print("[Instagram] Hashtag error " + str(resp.status_code) + " for #" + hashtag)
                return []

            data     = resp.json()
            sections = data.get("data", {}).get("recent", {}).get("sections", [])
            usernames = set()

            for section in sections:
                for layout in section.get("layout_content", {}).get("medias", []):
                    media = layout.get("media", {})
                    user  = media.get("user", {})
                    username = user.get("username", "")
                    if username:
                        usernames.add(username)

            print("[Instagram] #" + hashtag + " found " + str(len(usernames)) + " accounts")
            return list(usernames)[:max_accounts]

        except Exception as e:
            print("[Instagram] Hashtag exception: " + str(e))
            return []

    def get_profile(self, username):
        """Get full profile info for a username."""
        url = "https://www.instagram.com/api/v1/users/web_profile_info/?username=" + username
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 404:
                return None
            if resp.status_code == 429:
                print("[Instagram] Rate limited — waiting 60s")
                time.sleep(60)
                return None
            if resp.status_code != 200:
                return None

            user = resp.json().get("data", {}).get("user", {})
            if not user:
                return None
            return user

        except Exception as e:
            print("[Instagram] Profile error for " + username + ": " + str(e))
            return None

    def is_brand_account(self, user):
        """Returns True if this looks like a D2C brand, not a personal account."""
        bio      = (user.get("biography") or "").lower()
        name     = (user.get("full_name") or "").lower()
        category = (user.get("category_name") or "").lower()
        is_biz   = user.get("is_business_account", False)
        followers = user.get("edge_followed_by", {}).get("count", 0)

        # Skip personal accounts
        for skip in SKIP_KEYWORDS:
            if skip in bio or skip in name:
                return False

        # Must have a website link
        website = user.get("external_url") or user.get("bio_links", [{}])[0].get("url", "") if user.get("bio_links") else ""
        if not website:
            return False

        # Follower range: 1k to 500k (too big = already has agency, too small = not real biz)
        if followers < 1000 or followers > 500000:
            return False

        # Check brand signals
        has_brand_keyword = any(k in bio or k in name for k in BRAND_KEYWORDS)
        if is_biz or has_brand_keyword or "shop" in category or "retail" in category:
            return True

        return False

    def extract_email_from_bio(self, bio):
        """Extract email if mentioned in bio."""
        import re
        match = re.search(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', bio or "")
        return match.group(0) if match else ""

    def extract_city_from_bio(self, bio):
        """Try to extract Indian city from bio."""
        cities = [
            "mumbai", "delhi", "bangalore", "bengaluru", "hyderabad",
            "chennai", "kolkata", "pune", "ahmedabad", "surat",
            "jaipur", "lucknow", "kanpur", "nagpur", "indore",
            "thane", "bhopal", "visakhapatnam", "noida", "gurugram",
            "gurgaon", "chandigarh", "coimbatore", "kochi"
        ]
        bio_lower = (bio or "").lower()
        for city in cities:
            if city in bio_lower:
                return city.title()
        return "India"

    def score_pain_points(self, user, followers):
        """Determine pain points based on profile signals."""
        pain = []
        bio  = (user.get("biography") or "").lower()

        if followers < 10000:
            pain.append("low social media reach")
        if "dm" in bio or "whatsapp" in bio:
            pain.append("no proper website — selling via DMs")
        if not user.get("external_url"):
            pain.append("no website — missing online store")
        else:
            pain.append("poor SEO ranking")
            pain.append("low website traffic")
        if followers < 5000:
            pain.append("weak online presence")
        if "new" in bio or "launch" in bio or "started" in bio:
            pain.append("new brand needs digital foundation")

        return pain[:3]

    def scrape_leads(self, max_leads=100):
        """Main method — search hashtags and return brand leads."""
        leads      = []
        seen       = set()
        usernames  = []

        # Collect usernames from hashtags
        print("[Instagram] Searching " + str(len(INSTAGRAM_HASHTAGS)) + " hashtags...")
        for tag in INSTAGRAM_HASHTAGS:
            if len(usernames) >= max_leads * 3:
                break
            new_users = self.search_hashtag(tag, max_accounts=20)
            for u in new_users:
                if u not in seen:
                    seen.add(u)
                    usernames.append(u)
            time.sleep(2)  # be respectful

        print("[Instagram] Collected " + str(len(usernames)) + " unique usernames")

        # Get profiles and filter brands
        print("[Instagram] Fetching profiles...")
        for username in usernames:
            if len(leads) >= max_leads:
                break
            user = self.get_profile(username)
            if not user:
                time.sleep(1)
                continue

            if not self.is_brand_account(user):
                time.sleep(0.5)
                continue

            followers = user.get("edge_followed_by", {}).get("count", 0)
            following = user.get("edge_follow", {}).get("count", 0)
            posts     = user.get("edge_owner_to_timeline_media", {}).get("count", 0)
            bio       = user.get("biography") or ""
            website   = user.get("external_url") or ""
            if not website and user.get("bio_links"):
                website = user["bio_links"][0].get("url", "")

            email      = self.extract_email_from_bio(bio)
            city       = self.extract_city_from_bio(bio)
            pain       = self.score_pain_points(user, followers)
            category   = user.get("category_name") or "E-Commerce"
            full_name  = user.get("full_name") or username

            lead = InstagramLead(
                username=username,
                full_name=full_name,
                bio=bio[:200],
                website=website,
                email=email,
                followers=followers,
                following=following,
                posts=posts,
                profile_url="https://instagram.com/" + username,
                category=category,
                city=city,
                pain_points=pain,
                company=full_name,
                job_title="Founder / Owner",
            )
            leads.append(lead)
            print("[Instagram] Brand found: @" + username + " | " + str(followers) + " followers | " + website)
            time.sleep(1.5)

        print("[Instagram] Total brand leads: " + str(len(leads)))
        return leads


class InstagramLeadPipeline:
    def __init__(self):
        self.scraper = InstagramScraper()

    def run(self, max_leads=100):
        print("\n=== Instagram D2C Brand Scraper ===")
        leads = self.scraper.scrape_leads(max_leads=max_leads)

        if not leads:
            print("[Instagram] No leads found")
            return []

        # Save to DB
        try:
            from database import init_db, save_leads
            init_db()
            saved = save_leads([asdict(l) for l in leads])
            print("[Instagram] Saved " + str(saved) + " leads to DB")
        except Exception as e:
            print("[Instagram] DB error: " + str(e))
            with open("instagram_leads.json", "w") as f:
                json.dump([asdict(l) for l in leads], f, indent=2)

        return leads


if __name__ == "__main__":
    pipeline = InstagramLeadPipeline()
    leads = pipeline.run(max_leads=50)
    print("\nTop 5 Instagram leads:")
    for l in leads[:5]:
        print("@" + l.username + " | " + l.full_name + " | " + str(l.followers) + " followers | " + l.website)
