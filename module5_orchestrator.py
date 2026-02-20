"""
MODULE 5: ORCHESTRATOR
=======================
Runs the full sales pipeline automatically:
1. Find leads (IndiaMART scraper)
2. Enrich contacts (JustDial + Google)
3. Send WhatsApp outreach
4. Monitor replies and continue conversation
5. Trigger voice call when lead is warm
6. Track progress in DB

Schedule: runs daily via /orchestrator/run endpoint
"""
import os
import time
from datetime import datetime, timedelta

WHATSAPP_ENABLED  = os.getenv("WHATSAPP_ENABLED", "false").lower() == "true"
VAPI_ENABLED      = os.getenv("VAPI_ENABLED", "false").lower() == "true"
MAX_OUTREACH_DAY  = int(os.getenv("MAX_OUTREACH_DAY", "20"))  # max WhatsApp per day
FOLLOWUP_DAYS     = [2, 5, 10]  # days after first contact to follow up


class SalesOrchestrator:

    def __init__(self, log_fn=None):
        self.log = log_fn or print

    def run_full_pipeline(self, scrape_fresh=False, enrich=True, outreach=True):
        """Run the complete pipeline end to end."""
        self.log("[Orchestrator] Starting full pipeline...")
        results = {
            "scraped":  0,
            "enriched": 0,
            "messaged": 0,
            "errors":   []
        }

        # Step 1: Scrape fresh leads (optional)
        if scrape_fresh:
            self.log("[Orchestrator] Step 1: Scraping IndiaMART...")
            try:
                from indiamart_scraper import IndiaMartLeadPipeline
                pipeline = IndiaMartLeadPipeline()
                leads    = pipeline.run(max_per_category=25, clear_first=False)
                results["scraped"] = len(leads)
                self.log("[Orchestrator] Scraped " + str(len(leads)) + " new leads")
            except Exception as e:
                err = "Scrape error: " + str(e)
                self.log("[Orchestrator] " + err)
                results["errors"].append(err)
        else:
            self.log("[Orchestrator] Step 1: Skipping scrape (using existing leads)")

        # Step 2: Enrich contacts
        if enrich:
            self.log("[Orchestrator] Step 2: Enriching contacts...")
            try:
                from contact_finder import BulkContactEnricher
                enricher         = BulkContactEnricher()
                results["enriched"] = enricher.run(limit=30)
                self.log("[Orchestrator] Enriched " + str(results["enriched"]) + " leads")
            except Exception as e:
                err = "Enrich error: " + str(e)
                self.log("[Orchestrator] " + err)
                results["errors"].append(err)

        # Step 3: WhatsApp outreach to new leads
        if outreach:
            self.log("[Orchestrator] Step 3: WhatsApp outreach...")
            try:
                messaged = self.run_outreach()
                results["messaged"] = messaged
                self.log("[Orchestrator] Messaged " + str(messaged) + " leads")
            except Exception as e:
                err = "Outreach error: " + str(e)
                self.log("[Orchestrator] " + err)
                results["errors"].append(err)

        self.log("[Orchestrator] Pipeline complete: " + str(results))
        return results

    def run_outreach(self):
        """Send WhatsApp messages to new leads that haven't been contacted."""
        from database import load_leads
        from module4_outreach import WhatsAppManager

        wa    = WhatsAppManager()
        leads = load_leads(stage="new", limit=MAX_OUTREACH_DAY)
        sent  = 0

        for lead in leads:
            if sent >= MAX_OUTREACH_DAY:
                self.log("[Orchestrator] Daily outreach limit reached (" + str(MAX_OUTREACH_DAY) + ")")
                break

            phone = lead.get("phone", "")
            if not phone:
                self.log("[Outreach] No phone for " + lead.get("company", "?") + " — skipping")
                continue

            self.log("[Outreach] Messaging: " + lead.get("company", "") + " | " + phone)

            if WHATSAPP_ENABLED:
                success = wa.send_cold_outreach(lead)
                if success:
                    sent += 1
            else:
                # Simulation mode — just update stage
                self.log("[Outreach] SIMULATED (set WHATSAPP_ENABLED=true to send real messages)")
                try:
                    from database import update_lead_stage
                    update_lead_stage(lead["id"], "contacted")
                    sent += 1
                except Exception:
                    pass

            time.sleep(2)  # rate limit

        return sent

    def run_followups(self):
        """Send follow-ups to leads that haven't replied."""
        from database import load_leads
        from module4_outreach import WhatsAppManager

        wa    = WhatsAppManager()
        leads = load_leads(stage="contacted", limit=50)
        sent  = 0

        for lead in leads:
            # Check how long since contact
            created = lead.get("updated_at") or lead.get("created_at") or ""
            if not created:
                continue
            try:
                dt   = datetime.fromisoformat(created.replace("Z", ""))
                days = (datetime.utcnow() - dt).days
            except Exception:
                continue

            # Send follow-up on day 2, 5, or 10
            if days in FOLLOWUP_DAYS:
                followup_num = FOLLOWUP_DAYS.index(days) + 1
                phone = lead.get("phone", "")
                if not phone:
                    continue
                self.log("[Followup] Day " + str(days) + " followup to: " + lead.get("company", ""))
                if WHATSAPP_ENABLED:
                    wa.send_followup(lead, followup_num)
                    sent += 1
                else:
                    self.log("[Followup] SIMULATED followup #" + str(followup_num))
                    sent += 1
                time.sleep(2)

        self.log("[Followup] Sent " + str(sent) + " follow-ups")
        return sent

    def trigger_voice_call(self, lead):
        """Trigger a Vapi voice call for a warm lead."""
        if not VAPI_ENABLED:
            self.log("[Voice] VAPI_ENABLED=false — skipping call for " + lead.get("company", ""))
            return False
        try:
            from module3_voice_agent import VapiCaller
            caller = VapiCaller()
            result = caller.start_call(lead)
            self.log("[Voice] Call started for " + lead.get("company", "") + " | " + str(result))
            return True
        except Exception as e:
            self.log("[Voice] Error: " + str(e))
            return False

    def get_pipeline_summary(self):
        """Get current pipeline health metrics."""
        try:
            from database import count_by_stage, load_leads
            counts = count_by_stage()
            total  = sum(counts.values())
            leads  = load_leads(limit=500)

            has_phone   = sum(1 for l in leads if l.get("phone"))
            has_email   = sum(1 for l in leads if l.get("email"))
            reachable   = sum(1 for l in leads if l.get("phone") or l.get("email"))

            return {
                "total_leads":   total,
                "by_stage":      counts,
                "has_phone":     has_phone,
                "has_email":     has_email,
                "reachable":     reachable,
                "unreachable":   total - reachable,
                "conversion_rate": round((counts.get("closed", 0) / max(total, 1)) * 100, 1),
            }
        except Exception as e:
            return {"error": str(e)}
