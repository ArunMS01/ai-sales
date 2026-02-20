"""
MODULE 4: WHATSAPP OUTREACH
============================
Sends personalized WhatsApp messages to leads via Twilio.
Handles: cold outreach, follow-ups, AI replies to responses.
"""
import os
import json
import time
from datetime import datetime
from twilio.rest import Client as TwilioClient

TWILIO_ACCOUNT_SID   = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN    = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")


class WhatsAppManager:

    def __init__(self):
        if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
            self.client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        else:
            self.client = None
            print("[WhatsApp] No Twilio credentials — messages will be simulated")

    def send(self, to_phone, message):
        """Send WhatsApp message to a phone number."""
        if not to_phone:
            print("[WhatsApp] No phone number — skipping")
            return False

        # Clean phone number
        digits = ''.join(filter(str.isdigit, str(to_phone)))[-10:]
        if len(digits) != 10:
            print("[WhatsApp] Invalid phone: " + str(to_phone))
            return False

        to_wa = "whatsapp:+91" + digits

        if not self.client:
            print("[WhatsApp] SIMULATED to " + to_wa + ":\n" + message)
            return True

        try:
            msg = self.client.messages.create(
                from_=TWILIO_WHATSAPP_FROM,
                to=to_wa,
                body=message
            )
            print("[WhatsApp] Sent to " + digits + " | SID: " + msg.sid)
            return True
        except Exception as e:
            print("[WhatsApp] Error: " + str(e)[:100])
            return False

    def send_cold_outreach(self, lead):
        """Send first WhatsApp message to a new lead."""
        from module2_agent_brain import SalesAgentBrain
        agent   = SalesAgentBrain()
        message = agent.generate_opening_message(lead, channel="whatsapp")
        success = self.send(lead.get("phone"), message)
        if success:
            self._update_stage(lead.get("id"), "contacted")
        return success

    def send_followup(self, lead, followup_num=1):
        """Send follow-up message."""
        from module2_agent_brain import SalesAgentBrain
        agent   = SalesAgentBrain()
        message = agent.generate_followup(lead, followup_num, channel="whatsapp")
        return self.send(lead.get("phone"), message)

    def handle_inbound_whatsapp(self, from_number, body):
        """Handle incoming WhatsApp reply — find lead, run AI, reply."""
        from module2_agent_brain import SalesAgentBrain
        from database import load_leads

        # Find lead by phone number
        digits = ''.join(filter(str.isdigit, from_number))[-10:]
        leads  = load_leads(limit=500)
        lead   = next((l for l in leads if digits in str(l.get("phone", ""))), None)

        if not lead:
            lead = {"name": "Unknown", "website": "", "pain_points": [], "city": "India", "phone": digits}

        agent  = SalesAgentBrain()
        result = agent.chat(lead, body, channel="whatsapp")

        # Update stage in DB
        if lead.get("id") and result.get("stage"):
            self._update_stage(lead["id"], result["stage"])

        return result["response"]

    def _update_stage(self, lead_id, stage):
        if not lead_id:
            return
        try:
            from database import update_lead_stage
            update_lead_stage(lead_id, stage)
        except Exception as e:
            print("[WhatsApp] Stage update error: " + str(e))
