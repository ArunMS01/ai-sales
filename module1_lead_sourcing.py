import os
import json
import time
import requests
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional

RAPIDAPI_KEY   = os.getenv("RAPIDAPI_KEY", "")
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "")
HUBSPOT_API_KEY = os.getenv("HUBSPOT_API_KEY", "")
PAGESPEED_API_KEY = os.getenv("PAGESPEED_API_KEY", "")


@dataclass
class Lead:
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
    stage: str = "new"
    created_at: str = ""

    def __post_init__(self):
        if self.pain_points is None:
            self.pain_points = []
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()


# ── Source 1: LinkedIn via RapidAPI ──────────────────────────────────────────
class LinkedInScraper:
    """
    Uses RapidAPI LinkedIn endpoints to find e-commerce founders/owners.
    Tries multiple RapidAPI LinkedIn services for best results.
    """

    def __init__(self):
        self.headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": "",
            "Content-Type": "application/json"
        }

    def search_ecommerce_founders(self, location="India", max_results=50):
        """Search LinkedIn for e-commerce founders and marketing heads."""
        leads = []

        # Strategy 1: Fresh LinkedIn Profile Data API
        leads += self._search_fresh_linkedin(location, max_results)

        # Strategy 2: LinkedIn People Search API (fallback)
        if len(leads) < 10:
            leads += self._search_people_api(location, max_results)

        # Deduplicate by LinkedIn URL
        seen = set()
        unique = []
        for l in leads:
            key = l.linkedin_url or l.name
            if key not in seen:
                seen.add(key)
                unique.append(l)

        print("[LinkedIn] Found " + str(len(unique)) + " unique leads")
        return unique[:max_results]

    def _search_fresh_linkedin(self, location, max_results):
        """Fresh LinkedIn Profile Data (rapidapi.com/fresh-linkedin-profile-data)"""
        leads = []
        keywords_list = [
            "ecommerce founder India",
            "online store owner India",
            "shopify store founder India",
            "fashion ecommerce founder India",
            "d2c brand founder India",
        ]

        host = "fresh-linkedin-profile-data.p.rapidapi.com"
        self.headers["x-rapidapi-host"] = host

        for keyword in keywords_list:
            if len(leads) >= max_results:
                break
            try:
                resp = requests.get(
                    "https://" + host + "/search-people",
                    headers=self.headers,
                    params={
                        "keywords": keyword,
                        "geo_codes": "102713980",  # India geo code
                        "count": "10"
                    },
                    timeout=15
                )
                data = resp.json()

                if resp.status_code != 200:
                    print("[LinkedIn] Fresh API error: " + str(resp.status_code) + " " + str(data)[:100])
                    break

                for person in data.get("data", []):
                    lead = self._parse_fresh_profile(person)
                    if lead:
                        leads.append(lead)

                time.sleep(1)

            except Exception as e:
                print("[LinkedIn] Fresh API exception: " + str(e))
                break

        print("[LinkedIn-Fresh] Got " + str(len(leads)) + " leads")
        return leads

    def _search_people_api(self, location, max_results):
        """LinkedIn People Search API fallback"""
        leads = []
        searches = [
            {"keywords": "ecommerce founder", "title": "Founder"},
            {"keywords": "online store owner", "title": "Owner"},
            {"keywords": "shopify india marketing", "title": "Marketing"},
        ]

        host = "linkedin-data-api.p.rapidapi.com"
        self.headers["x-rapidapi-host"] = host

        for search in searches:
            if len(leads) >= max_results:
                break
            try:
                resp = requests.get(
                    "https://" + host + "/search-people",
                    headers=self.headers,
                    params={
                        "keywords": search["keywords"],
                        "locationFilter": location,
                        "titleFilter": search["title"],
                        "start": "0"
                    },
                    timeout=15
                )
                data = resp.json()

                if resp.status_code != 200:
                    print("[LinkedIn] People API error: " + str(resp.status_code))
                    break

                for person in data.get("items", data.get("data", [])):
                    lead = self._parse_people_profile(person)
                    if lead:
                        leads.append(lead)

                time.sleep(1.5)

            except Exception as e:
                print("[LinkedIn] People API exception: " + str(e))
                break

        print("[LinkedIn-People] Got " + str(len(leads)) + " leads")
        return leads

    def _parse_fresh_profile(self, person):
        """Parse profile from Fresh LinkedIn API response."""
        try:
            full_name = (person.get("firstName", "") + " " + person.get("lastName", "")).strip()
            if not full_name:
                return None

            title     = person.get("headline", "") or person.get("title", "")
            company   = ""
            website   = ""
            city      = person.get("geoRegion", "") or person.get("location", "")
            linkedin  = person.get("profileURL", "") or person.get("url", "")

            # Extract company from experience
            experiences = person.get("experiences", []) or person.get("positions", {}).get("positionHistory", [])
            if experiences:
                latest = experiences[0]
                company = latest.get("companyName", "") or latest.get("company", "")
                website = latest.get("companyURL", "") or ""

            # Filter: only keep founders, owners, CEOs, marketing roles
            title_lower = title.lower()
            relevant = any(t in title_lower for t in [
                "founder", "owner", "ceo", "co-founder", "director",
                "head of marketing", "marketing manager", "entrepreneur", "md"
            ])
            if not relevant:
                return None

            return Lead(
                name=full_name,
                website=website,
                phone="",
                email="",
                city=city,
                source="linkedin",
                linkedin_url=linkedin,
                job_title=title,
                company=company
            )
        except Exception as e:
            print("[LinkedIn] Parse error: " + str(e))
            return None

    def _parse_people_profile(self, person):
        """Parse profile from LinkedIn People Search API response."""
        try:
            full_name = person.get("fullName", "") or (
                person.get("firstName", "") + " " + person.get("lastName", "")
            ).strip()
            if not full_name:
                return None

            title    = person.get("title", "") or person.get("headline", "")
            company  = person.get("companyName", "") or person.get("company", "")
            city     = person.get("location", "") or person.get("geoRegion", "")
            linkedin = person.get("profileURL", "") or person.get("url", "")

            title_lower = title.lower()
            relevant = any(t in title_lower for t in [
                "founder", "owner", "ceo", "co-founder", "director",
                "head of marketing", "marketing manager", "entrepreneur"
            ])
            if not relevant:
                return None

            return Lead(
                name=full_name,
                website="",
                phone="",
                email="",
                city=city,
                source="linkedin",
                linkedin_url=linkedin,
                job_title=title,
                company=company
            )
        except Exception as e:
            print("[LinkedIn] Parse error: " + str(e))
            return None

    def get_profile_details(self, linkedin_url):
        """Get full profile + contact info for a specific LinkedIn URL."""
        host = "fresh-linkedin-profile-data.p.rapidapi.com"
        self.headers["x-rapidapi-host"] = host
        try:
            resp = requests.get(
                "https://" + host + "/get-linkedin-profile",
                headers=self.headers,
                params={"linkedin_url": linkedin_url, "include_skills": "false"},
                timeout=15
            )
            return resp.json().get("data", {})
        except Exception as e:
            print("[LinkedIn] Profile fetch error: " + str(e))
            return {}


# ── Source 2: Apollo Email Enrichment (find email from company name) ──────────
class ApolloEnricher:
    BASE_URL = "https://api.apollo.io/v1"

    def __init__(self):
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": APOLLO_API_KEY or ""
        }

    def enrich_lead(self, lead):
        """Find email for a lead using their name + company."""
        if lead.email:
            return lead

        query = lead.company or lead.name
        if not query:
            return lead

        payload = {
            "q_keywords": query,
            "person_titles": ["CEO", "Founder", "Owner", "Co-Founder", "Marketing Manager"],
            "per_page": 5,
            "page": 1
        }
        try:
            resp = requests.post(
                self.BASE_URL + "/mixed_people/search",
                headers=self.headers,
                json=payload,
                timeout=10
            ).json()

            for person in resp.get("people", []):
                name_match = lead.name.lower() in (person.get("name") or "").lower()
                if name_match and person.get("email"):
                    lead.email   = person["email"]
                    lead.website = lead.website or (person.get("organization") or {}).get("website_url", "")
                    print("  [Apollo] Found email for " + lead.name + ": " + lead.email)
                    break
        except Exception as e:
            print("  [Apollo] Enrich error: " + str(e))
        return lead


# ── Source 3: SEO Scorer ──────────────────────────────────────────────────────
class SEOScorer:
    def score_lead(self, lead):
        if not lead.website:
            return lead
        import urllib.parse
        url = (
            "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
            "?url=" + urllib.parse.quote(lead.website) +
            "&strategy=mobile&key=" + (PAGESPEED_API_KEY or "")
        )
        try:
            resp = requests.get(url, timeout=15).json()
            cats = resp.get("lighthouseResult", {}).get("categories", {})
            perf = cats.get("performance", {}).get("score", 1)
            seo  = cats.get("seo", {}).get("score", 1)
            lead.pagespeed_score = int(perf * 100)
            lead.seo_score       = int(seo * 100)
            if lead.pagespeed_score < 50:
                lead.pain_points.append("slow website speed")
            if lead.seo_score < 60:
                lead.pain_points.append("poor SEO ranking")
            print("  [SEO] " + lead.website + " Speed:" + str(lead.pagespeed_score) + " SEO:" + str(lead.seo_score))
        except Exception as e:
            print("  [SEO] Failed: " + str(e))
        return lead

    def prioritize(self, leads):
        def score(l):
            return (l.seo_score or 100) + (l.pagespeed_score or 100)
        return sorted(leads, key=score)


# ── HubSpot Sync ──────────────────────────────────────────────────────────────
class HubSpotSync:
    BASE_URL = "https://api.hubapi.com/crm/v3"

    def __init__(self):
        self.headers = {
            "Authorization": "Bearer " + (HUBSPOT_API_KEY or ""),
            "Content-Type": "application/json"
        }

    def upsert_contact(self, lead):
        name_parts = lead.name.split()
        payload = {
            "properties": {
                "firstname":      name_parts[0] if name_parts else "",
                "lastname":       " ".join(name_parts[1:]) if len(name_parts) > 1 else "",
                "email":          lead.email,
                "phone":          lead.phone,
                "website":        lead.website,
                "city":           lead.city,
                "jobtitle":       lead.job_title,
                "company":        lead.company,
                "hs_lead_status": lead.stage.upper(),
                "linkedin_url__c": lead.linkedin_url,
            }
        }
        try:
            resp = requests.post(
                self.BASE_URL + "/objects/contacts",
                headers=self.headers,
                json=payload,
                timeout=10
            )
            if resp.status_code == 409:
                contact_id = resp.json().get("message", "").split("ID: ")[-1].strip()
                requests.patch(
                    self.BASE_URL + "/objects/contacts/" + contact_id,
                    headers=self.headers,
                    json=payload,
                    timeout=10
                )
        except Exception as e:
            print("  [HubSpot] Error: " + str(e))


# ── Main Pipeline ─────────────────────────────────────────────────────────────
class LeadSourcingPipeline:
    def __init__(self):
        self.linkedin  = LinkedInScraper()
        self.apollo    = ApolloEnricher()
        self.seo       = SEOScorer()
        self.hubspot   = HubSpotSync()

    def run(self, cities=None, max_leads=100):
        all_leads = []

        print("\n=== STEP 1: LinkedIn Lead Search ===")
        linkedin_leads = self.linkedin.search_ecommerce_founders(
            location="India", max_results=max_leads
        )
        all_leads.extend(linkedin_leads)
        print("Total after LinkedIn: " + str(len(all_leads)))

        print("\n=== STEP 2: Email Enrichment via Apollo ===")
        for i, lead in enumerate(all_leads):
            if not lead.email:
                all_leads[i] = self.apollo.enrich_lead(lead)
            time.sleep(0.3)

        print("\n=== STEP 3: SEO Scoring ===")
        for i, lead in enumerate(all_leads):
            if lead.website:
                all_leads[i] = self.seo.score_lead(lead)
            time.sleep(0.3)

        all_leads = self.seo.prioritize(all_leads)

        with open("leads.json", "w") as f:
            json.dump([asdict(l) for l in all_leads], f, indent=2)
        print("\nSaved " + str(len(all_leads)) + " leads to leads.json")

        print("\n=== STEP 4: HubSpot Sync ===")
        synced = 0
        for lead in all_leads:
            if lead.email or lead.linkedin_url:
                self.hubspot.upsert_contact(lead)
                synced += 1
        print("Synced " + str(synced) + " leads to HubSpot")

        return all_leads


if __name__ == "__main__":
    pipeline = LeadSourcingPipeline()
    leads = pipeline.run(max_leads=100)
    print("\nTop 5 leads:")
    for l in leads[:5]:
        print(l.name, "|", l.company, "|", l.email, "|", l.linkedin_url)
