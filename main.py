"""
main.py — Railway Entry Point
==============================
Single FastAPI app that runs everything:
  - /health         → Railway health check
  - /vapi/webhook   → Handles Vapi call events
  - /twilio/webhook → Handles incoming WhatsApp replies
  - /leads/run      → Manually trigger lead sourcing
  - /leads/list     → View current leads
  - /agent/chat     → Test the AI brain via API
  - Background scheduler for follow-ups + outreach
"""

import os
import json
import time
import threading
from datetime import datetime
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse
from twilio.twiml.messaging_response import MessagingResponse

load_dotenv()

# ── Background scheduler thread ───────────────────────────────────────────────
scheduler_thread = None

def start_scheduler():
    """Run orchestrator scheduler in a background thread."""
    try:
        from module5_orchestrator import SalesAgentOrchestrator
        orch = SalesAgentOrchestrator()
        orch.start()
    except Exception as e:
        print(f"[Scheduler] Error: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background scheduler AFTER app is ready."""
    global scheduler_thread
    print("🚀 AI Sales Agent starting on Railway...")

    def delayed_start():
        time.sleep(15)  # wait for health check to pass first
        start_scheduler()

    scheduler_thread = threading.Thread(target=delayed_start, daemon=True)
    scheduler_thread.start()
    print("✅ App ready. Scheduler starting in 15s...")
    yield
    print("Shutting down...")

# ── FastAPI App ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Sales Agent",
    description="Automated sales agent for digital marketing agency",
    lifespan=lifespan
)


# ── Health Check (required by Railway) ───────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ── Dashboard (simple status page) ───────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    try:
        with open("leads.json") as f:
            leads = json.load(f)
    except FileNotFoundError:
        leads = []

    stage_counts = {}
    for l in leads:
        s = l.get("stage", "unknown")
        stage_counts[s] = stage_counts.get(s, 0) + 1

    rows = "".join([
        f"<tr><td>{l.get('name','')}</td><td>{l.get('website','')}</td>"
        f"<td>{l.get('stage','')}</td><td>{l.get('phone','')}</td></tr>"
        for l in leads[:20]
    ])

    return f"""
    <html>
    <head>
      <title>AI Sales Agent</title>
      <style>
        body {{ font-family: Arial, sans-serif; background: #0f1117; color: #e2e8f0; padding: 30px; }}
        h1 {{ color: #a78bfa; }} h2 {{ color: #6366f1; margin-top: 30px; }}
        .stat {{ display: inline-block; background: #1e2130; border-radius: 10px; padding: 16px 28px; margin: 8px; text-align: center; }}
        .stat .num {{ font-size: 2rem; font-weight: bold; color: #a78bfa; }}
        .stat .label {{ font-size: 0.8rem; color: #64748b; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
        th {{ background: #1e2130; padding: 10px; text-align: left; color: #6366f1; }}
        td {{ padding: 8px 10px; border-bottom: 1px solid #1e2130; font-size: 0.85rem; }}
      </style>
    </head>
    <body>
      <h1>🤖 AI Sales Agent — Live Dashboard</h1>
      <p style="color:#64748b">Running on Railway · {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>

      <div>
        <div class="stat"><div class="num">{len(leads)}</div><div class="label">Total Leads</div></div>
        <div class="stat"><div class="num">{stage_counts.get('new', 0)}</div><div class="label">New</div></div>
        <div class="stat"><div class="num">{stage_counts.get('contacted', 0)}</div><div class="label">Contacted</div></div>
        <div class="stat"><div class="num">{stage_counts.get('pitched', 0)}</div><div class="label">Pitched</div></div>
        <div class="stat"><div class="num">{stage_counts.get('closed', 0)}</div><div class="label">Closed 🎉</div></div>
      </div>

      <h2>Recent Leads</h2>
      <table>
        <tr><th>Name</th><th>Website</th><th>Stage</th><th>Phone</th></tr>
        {rows if rows else '<tr><td colspan="4" style="color:#64748b">No leads yet — hit /leads/run to source leads</td></tr>'}
      </table>

      <h2>Quick Actions</h2>
      <p>
        <a href="/leads/run" style="background:#6366f1;color:white;padding:10px 20px;border-radius:8px;text-decoration:none;margin-right:10px">▶ Source New Leads</a>
        <a href="/leads/list" style="background:#1e2130;color:#a78bfa;padding:10px 20px;border-radius:8px;text-decoration:none;border:1px solid #3730a3">📋 View All Leads (JSON)</a>
      </p>
    </body>
    </html>
    """


# ── Vapi Webhook ──────────────────────────────────────────────────────────────
@app.post("/vapi/webhook")
async def vapi_webhook(request: Request):
    body = await request.json()
    event_type = body.get("message", {}).get("type", "")
    call_id    = body.get("message", {}).get("call", {}).get("id", "")
    print(f"[Vapi] Event: {event_type} | Call: {call_id}")

    if event_type == "call-ended":
        from module5_orchestrator import SalesAgentOrchestrator
        orch = SalesAgentOrchestrator()
        await orch.post_call_processing(call_id, body.get("message", {}))

    elif event_type == "function-call":
        from module3_voice_agent import handle_function_call
        fn   = body["message"].get("functionCall", {}).get("name", "")
        args = body["message"].get("functionCall", {}).get("parameters", {})
        result = await handle_function_call(fn, args, call_id)
        return JSONResponse({"result": result})

    return JSONResponse({"status": "ok"})


# ── Twilio Webhook ────────────────────────────────────────────────────────────
@app.post("/twilio/webhook")
async def twilio_webhook(request: Request):
    form = await request.form()
    from_number = form.get("From", "").replace("whatsapp:", "")
    body        = form.get("Body", "")

    print(f"[WhatsApp] From: {from_number} | Message: {body[:80]}")

    from module4_outreach import WhatsAppManager
    wa = WhatsAppManager()
    ai_reply = wa.handle_inbound_whatsapp(from_number, body)

    resp = MessagingResponse()
    resp.message(ai_reply)
    return HTMLResponse(content=str(resp), media_type="application/xml")


# ── Manual Triggers ───────────────────────────────────────────────────────────
@app.get("/leads/run")
async def run_lead_sourcing(background_tasks: BackgroundTasks):
    def _run():
        from module1_lead_sourcing import LeadSourcingPipeline
        pipeline = LeadSourcingPipeline()
        pipeline.run(cities=["Mumbai", "Delhi", "Bangalore"], max_leads=100)
    background_tasks.add_task(_run)
    return {"status": "started", "message": "Lead sourcing running in background. Check /leads/list in ~5 minutes."}


@app.get("/leads/list")
async def list_leads(stage: str = None, limit: int = 50):
    try:
        with open("leads.json") as f:
            leads = json.load(f)
        if stage:
            leads = [l for l in leads if l.get("stage") == stage]
        return {"total": len(leads), "leads": leads[:limit]}
    except FileNotFoundError:
        return {"total": 0, "leads": [], "message": "No leads yet. Hit /leads/run first."}


@app.post("/agent/chat")
async def test_agent(request: Request):
    body    = await request.json()
    lead    = body.get("lead", {"name": "Test", "website": "test.com", "pain_points": [], "stage": "new"})
    message = body.get("message", "Hello")
    channel = body.get("channel", "whatsapp")

    from module2_agent_brain import SalesAgentBrain
    agent = SalesAgentBrain()
    result = agent.chat(lead, message, channel=channel)
    return result


@app.post("/deals/close")
async def close_deal(request: Request):
    body    = await request.json()
    email   = body.get("lead_email")
    package = body.get("package", "growth")

    from module5_orchestrator import LeadStateManager, DealCloser
    state = LeadStateManager()
    leads = state.load_all()
    lead  = next((l for l in leads if l.get("email") == email), None)

    if not lead:
        return JSONResponse({"error": "Lead not found"}, status_code=404)

    closer = DealCloser()
    result = closer.close_deal(lead, package)
    return result
