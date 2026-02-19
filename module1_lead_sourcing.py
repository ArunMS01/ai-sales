import os
import json
import time
import requests
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional
import urllib.parse

GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
APOLLO_API_KEY        = os.getenv("APOLLO_API_KEY")
HUBSPOT_API_KEY       = os.getenv("HUBSPOT_API_KEY")
PAGESPEED_API_KEY     = os.getenv("PAGESPEED_API_KEY")


@dataclass
class Lead:
    name: str
    website: str
    phone: str
    email: str
    city: str
    source: str
    seo_score: Optional[int] = None
    pagespeed_score: Optional[int] = None
    has_google_ads: Optional[bool] = None
    pain_points: list = None
    stage: str = "new"
    created_at: str = ""

    def __post_init__(self):
        if self.pain_points is None:
            self.pain_points = []
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()


class GoogleMapsLeadScraper:
    BASE_URL = "https://maps.googleapis.com/maps/api/place"
    QUERIES = [
        "clothing boutique",
        "electronics shop",
        "fashion store",
        "jewellery shop",
        "home decor store",
        "shoe store",
        "online shopping",
    ]

    def __init__(self):
        self.api_key = GOOGLE_PLACES_API_KEY

    def search_leads(self, query: str, location: str, max_results: int = 20):
        leads = []
        url = self.BASE_URL + "/textsearch/json"

        for q in self.QUERIES:
            if len(leads) >= max_results:
                break
            params = {
                "query": q + " in " + location,
                "key": self.api_key,
            }
            try:
                resp = requests.get(url, params=params, timeout=10).json()
                status = resp.get("status", "")
                if status not in ("OK", "ZERO_RESULTS"):
                    print("[Google Maps] API error: " + status)
                    continue
                for place in resp.get("results", []):
                    details = self._get_place_details(place["place_id"])
                    website = details.get("website", "")
                    phone   = details.get("formatted_phone_number", "")
                    if not website:
                        continue
                    lead = Lead(
                        name=place.get("name", ""),
                        website=website,
                        phone=phone,
                        email="",
                        city=location,
                        source="google_maps"
                    )
                    leads.append(lead)
                    if len(leads) >= max_results:
                        break
            except Exception as e:
                print("[Google Maps] Error: " + str(e))
            time.sleep(0.5)

        print("[Google Maps] Found " + str(len(leads)) + " leads in " + location)
        return leads

    def _get_place_details(self, place_id):
        resp = requests.get(
            self.BASE_URL + "/details/json",
            params={
                "place_id": place_id,
                "fields": "website,formatted_phone_number",
                "key": self.api_key
            }
        ).json()
        return resp.get("result", {})


class ApolloEnricher:
    BASE_URL = "https://api.apollo.io/v1"

    def __init__(self):
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": APOLLO_API_KEY or ""
        }

    def enrich_lead(self, lead):
        if not lead.website:
            return lead
        domain = urllib.parse.urlparse(lead.website).netloc.replace("www.", "")
        payload = {
            "domain": domain,
            "titles": ["CEO", "Founder", "Marketing Manager", "Owner", "CMO"]
        }
        try:
            resp = requests.post(
                self.BASE_URL + "/mixed_people/search",
                headers=self.headers,
                json=payload,
                timeout=10
            ).json()
            people = resp.get("people", [])
            if people:
                top = people[0]
                lead.name  = top.get("name", lead.name)
                lead.email = top.get("email", "")
                print("  [Apollo] Enriched: " + lead.name + " at " + domain)
        except Exception as e:
            print("  [Apollo] Enrich error: " + str(e))
        return lead

    def search_ecommerce_companies(self, country="India", max=50):
        payload = {
            "q_keywords": "ecommerce online store shopify",
            "person_titles": ["CEO", "Founder", "Owner", "Co-Founder", "Marketing Manager"],
            "person_locations": [country],
            "per_page": min(max, 25),
            "page": 1
        }
        try:
            resp = requests.post(
                self.BASE_URL + "/mixed_people/search",
                headers=self.headers,
                json=payload,
                timeout=15
            ).json()
            if "error" in resp:
                print("  [Apollo] Error: " + str(resp["error"]))
                return []
            leads = []
            for person in resp.get("people", []):
                org     = person.get("organization") or {}
                website = org.get("website_url") or ""
                if not website:
                    continue
                phones = person.get("phone_numbers") or []
                phone  = phones[0].get("sanitized_number", "") if phones else ""
                leads.append(Lead(
                    name=person.get("name", ""),
                    website=website,
                    phone=phone,
                    email=person.get("email", ""),
                    city=org.get("city", country),
                    source="apollo"
                ))
            print("[Apollo] Found " + str(len(leads)) + " e-commerce leads")
            return leads
        except Exception as e:
            print("  [Apollo] Exception: " + str(e))
            return []


class SEOScorer:
    def score_lead(self, lead):
        if not lead.website:
            return lead
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
                "firstname": name_parts[0] if name_parts else "",
                "lastname":  " ".join(name_parts[1:]) if len(name_parts) > 1 else "",
                "email":     lead.email,
                "phone":     lead.phone,
                "website":   lead.website,
                "city":      lead.city,
                "hs_lead_status": lead.stage.upper(),
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
                contact_id = resp.json().get("message", "").split("ID: ")[-1]
                requests.patch(
                    self.BASE_URL + "/objects/contacts/" + contact_id,
                    headers=self.headers,
                    json=payload,
                    timeout=10
                )
        except Exception as e:
            print("  [HubSpot] Error: " + str(e))


class LeadSourcingPipeline:
    def __init__(self):
        self.maps_scraper = GoogleMapsLeadScraper()
        self.apollo       = ApolloEnricher()
        self.seo_scorer   = SEOScorer()
        self.hubspot      = HubSpotSync()

    def run(self, cities=None, max_leads=200):
        if cities is None:
            cities = ["Mumbai", "Delhi", "Bangalore"]

        all_leads = []

        print("\n=== STEP 1: Google Maps Scraping ===")
        for city in cities:
            leads = self.maps_scraper.search_leads("store", city, max_results=20)
            all_leads.extend(leads)

        print("\n=== STEP 2: Apollo.io Search ===")
        apollo_leads = self.apollo.search_ecommerce_companies(max=50)
        all_leads.extend(apollo_leads)

        print("\n=== STEP 3: Email Enrichment ===")
        for i, lead in enumerate(all_leads):
            if not lead.email and lead.website:
                all_leads[i] = self.apollo.enrich_lead(lead)

        print("\n=== STEP 4: SEO Scoring ===")
        for i, lead in enumerate(all_leads):
            if lead.website:
                all_leads[i] = self.seo_scorer.score_lead(lead)
            time.sleep(0.3)

        all_leads = self.seo_scorer.prioritize(all_leads)

        with open("leads.json", "w") as f:
            json.dump([asdict(l) for l in all_leads], f, indent=2)
        print("\nSaved " + str(len(all_leads)) + " leads to leads.json")

        print("\n=== STEP 5: HubSpot Sync ===")
        for lead in all_leads[:max_leads]:
            self.hubspot.upsert_contact(lead)
        print("Synced to HubSpot")

        return all_leads


if __name__ == "__main__":
    pipeline = LeadSourcingPipeline()
    leads = pipeline.run(cities=["Mumbai", "Delhi", "Bangalore"], max_leads=200)
    print("\nTop 5 leads:")
    for l in leads[:5]:
        print(l.name, "|", l.website, "| SEO:", l.seo_score)
