import os
import json
import time
import requests
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional

APOLLO_API_KEY    = os.getenv("APOLLO_API_KEY", "")
HUBSPOT_API_KEY   = os.getenv("HUBSPOT_API_KEY", "")
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


class ApolloSource:
    BASE_URL = "https://api.apollo.io/v1"

    def __init__(self):
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": APOLLO_API_KEY
        }

    def search_leads(self, max=100):
        all_leads = []
        seen = set()

        searches = [
            {"keywords": "ecommerce",        "titles": ["Founder", "CEO", "Owner", "Co-Founder"]},
            {"keywords": "online store",     "titles": ["Founder", "CEO", "Owner"]},
            {"keywords": "shopify",          "titles": ["Founder", "CEO", "Owner", "Co-Founder"]},
            {"keywords": "fashion brand",    "titles": ["Founder", "Director", "Owner"]},
            {"keywords": "d2c brand",        "titles": ["Founder", "CEO", "CMO", "Marketing Head"]},
            {"keywords": "ecommerce",        "titles": ["Marketing Manager", "Head of Marketing", "CMO"]},
            {"keywords": "retail online",    "titles": ["Founder", "Owner", "CEO"]},
        ]

        for s in searches:
            if len(all_leads) >= max:
                break
            try:
                payload = {
                    "q_keywords":       s["keywords"],
                    "person_titles":    s["titles"],
                    "person_locations": ["India"],
                    "per_page":         25,
                    "page":             1
                }
                resp = requests.post(
                    self.BASE_URL + "/mixed_people/search",
                    headers={"Content-Type": "application/json", "x-api-key": APOLLO_API_KEY},
                    json=payload,
                    timeout=20
                )
                print("[Apollo] Status: " + str(resp.status_code) + " for: " + s["keywords"])

                if resp.status_code != 200:
                    print("[Apollo] Response: " + resp.text[:200])
                    continue

                data = resp.json()
                people = data.get("people", [])
                print("[Apollo] Got " + str(len(people)) + " people for: " + s["keywords"])

                for person in people:
                    name = person.get("name", "")
                    if not name or name in seen:
                        continue
                    seen.add(name)

                    org      = person.get("organization") or {}
                    website  = org.get("website_url") or ""
                    email    = person.get("email") or ""
                    title    = person.get("title") or ""
                    city     = org.get("city") or person.get("city") or "India"
                    company  = org.get("name") or ""
                    linkedin = person.get("linkedin_url") or ""
                    phones   = person.get("phone_numbers") or []
                    phone    = phones[0].get("sanitized_number", "") if phones else ""

                    all_leads.append(Lead(
                        name=name,
                        website=website,
                        phone=phone,
                        email=email,
                        city=city,
                        source="apollo",
                        linkedin_url=linkedin,
                        job_title=title,
                        company=company
                    ))

                time.sleep(1)

            except Exception as e:
                print("[Apollo] Exception for " + s["keywords"] + ": " + str(e))

        print("[Apollo] Total unique leads: " + str(len(all_leads)))
        return all_leads[:max]


class SEOScorer:
    def score_lead(self, lead):
        if not lead.website:
            return lead
        import urllib.parse
        url = (
            "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
            "?url=" + urllib.parse.quote(lead.website)
            + "&strategy=mobile&key=" + PAGESPEED_API_KEY
        )
        try:
            resp = requests.get(url, timeout=15).json()
            cats = resp.get("lighthouseResult", {}).get("categories", {})
            lead.pagespeed_score = int(cats.get("performance", {}).get("score", 1) * 100)
            lead.seo_score       = int(cats.get("seo",         {}).get("score", 1) * 100)
            if lead.pagespeed_score < 50:
                lead.pain_points.append("slow website speed")
            if lead.seo_score < 60:
                lead.pain_points.append("poor SEO ranking")
            print("  [SEO] " + lead.website + " speed=" + str(lead.pagespeed_score) + " seo=" + str(lead.seo_score))
        except Exception as e:
            print("  [SEO] Failed: " + str(e))
        return lead

    def prioritize(self, leads):
        return sorted(leads, key=lambda l: (l.seo_score or 100) + (l.pagespeed_score or 100))


class HubSpotSync:
    BASE_URL = "https://api.hubapi.com/crm/v3"

    def __init__(self):
        self.headers = {
            "Authorization": "Bearer " + HUBSPOT_API_KEY,
            "Content-Type":  "application/json"
        }

    def upsert_contact(self, lead):
        parts = lead.name.split()
        payload = {
            "properties": {
                "firstname":      parts[0] if parts else "",
                "lastname":       " ".join(parts[1:]) if len(parts) > 1 else "",
                "email":          lead.email,
                "phone":          lead.phone,
                "website":        lead.website,
                "city":           lead.city,
                "jobtitle":       lead.job_title,
                "company":        lead.company,
                "hs_lead_status": "NEW",
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
                cid = resp.json().get("message", "").split("ID: ")[-1].strip()
                requests.patch(
                    self.BASE_URL + "/objects/contacts/" + cid,
                    headers=self.headers,
                    json=payload,
                    timeout=10
                )
                return
            if resp.status_code not in (200, 201):
                print("  [HubSpot] Error " + str(resp.status_code) + ": " + resp.text[:100])
        except Exception as e:
            print("  [HubSpot] Error: " + str(e))


class LeadSourcingPipeline:
    def __init__(self):
        self.apollo  = ApolloSource()
        self.seo     = SEOScorer()
        self.hubspot = HubSpotSync()

    def run(self, cities=None, max_leads=100):
        print("\n=== STEP 1: Apollo Search ===")
        leads = self.apollo.search_leads(max=max_leads)

        if not leads:
            print("[Pipeline] No leads from Apollo. Check APOLLO_API_KEY in Railway Variables.")
            return []

        print("\n=== STEP 2: SEO Scoring ===")
        for i, lead in enumerate(leads):
            if lead.website:
                leads[i] = self.seo.score_lead(lead)
            time.sleep(0.2)

        leads = self.seo.prioritize(leads)

        with open("leads.json", "w") as f:
            json.dump([asdict(l) for l in leads], f, indent=2)
        print("\nSaved " + str(len(leads)) + " leads to leads.json")

        print("\n=== STEP 3: HubSpot Sync ===")
        synced = 0
        for lead in leads:
            self.hubspot.upsert_contact(lead)
            synced += 1
        print("Synced " + str(synced) + " to HubSpot")

        return leads


if __name__ == "__main__":
    pipeline = LeadSourcingPipeline()
    leads = pipeline.run(max_leads=100)
    print("\nTop 5:")
    for l in leads[:5]:
        print(l.name, "|", l.company, "|", l.email, "|", l.city)
