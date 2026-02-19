import os
import json
import time
import threading
from datetime import datetime
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("✅ App ready.")
    yield

app = FastAPI(title="AI Sales Agent", lifespan=lifespan)

# ── Health Check ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    try:
        from database import init_db, load_leads, count_by_stage
        init_db()
        leads = load_leads(limit=20)
        stage_counts = count_by_stage()
    except:
        leads = []
        stage_counts = {}



    rows = "".join([
        f"<tr><td>{l.get('name','')}</td><td>{l.get('website','')}</td>"
        f"<td>{l.get('stage','')}</td><td>{l.get('phone','')}</td></tr>"
        for l in leads[:20]
    ])

    return f"""
    <html><head><title>AI Sales Agent</title>
    <style>
      body {{ font-family: Arial, sans-serif; background: #0f1117; color: #e2e8f0; padding: 30px; }}
      h1 {{ color: #a78bfa; }} h2 {{ color: #6366f1; margin-top: 30px; }}
      .stat {{ display: inline-block; background: #1e2130; border-radius: 10px; padding: 16px 28px; margin: 8px; text-align: center; }}
      .stat .num {{ font-size: 2rem; font-weight: bold; color: #a78bfa; }}
      .stat .label {{ font-size: 0.8rem; color: #64748b; }}
      table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
      th {{ background: #1e2130; padding: 10px; text-align: left; color: #6366f1; }}
      td {{ padding: 8px 10px; border-bottom: 1px solid #1e2130; font-size: 0.85rem; }}
      a.btn {{ background:#6366f1; color:white; padding:10px 20px; border-radius:8px; text-decoration:none; margin-right:10px; }}
    </style></head>
    <body>
      <h1>🤖 AI Sales Agent — Live</h1>
      <p style="color:#64748b">{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>
      <div>
        <div class="stat"><div class="num">{len(leads)}</div><div class="label">Total Leads</div></div>
        <div class="stat"><div class="num">{stage_counts.get('new',0)}</div><div class="label">New</div></div>
        <div class="stat"><div class="num">{stage_counts.get('contacted',0)}</div><div class="label">Contacted</div></div>
        <div class="stat"><div class="num">{stage_counts.get('pitched',0)}</div><div class="label">Pitched</div></div>
        <div class="stat"><div class="num">{stage_counts.get('closed',0)}</div><div class="label">Closed 🎉</div></div>
      </div>
      <h2>Recent Leads</h2>
      <table>
        <tr><th>Name</th><th>Website</th><th>Stage</th><th>Phone</th></tr>
        {rows if rows else '<tr><td colspan="4" style="color:#64748b">No leads yet — hit /leads/run</td></tr>'}
      </table>
      <h2>Actions</h2>
      <a class="btn" href="/leads/run">▶ Source Leads</a>
      <a class="btn" href="/test-keys" style="background:#1e2130;border:1px solid #6366f1">🔑 Test Keys</a>
      <a class="btn" href="/docs" style="background:#1e2130;border:1px solid #6366f1">📖 API Docs</a>
    </body></html>
    """

# ── Test Keys ─────────────────────────────────────────────────────────────────
@app.get("/test-keys")
async def test_keys():
    import requests as req
    results = {}

    try:
        import openai
        openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY")).models.list()
        results["openai"] = "✅ Connected"
    except Exception as e:
        results["openai"] = f"❌ {str(e)[:80]}"

    try:
        key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
        r = req.get(f"https://maps.googleapis.com/maps/api/place/textsearch/json?query=test&key={key}", timeout=5)
        results["google_places"] = "✅ Connected" if r.status_code == 200 else f"❌ {r.status_code}: {r.text[:60]}"
    except Exception as e:
        results["google_places"] = f"❌ {str(e)[:80]}"

    try:
        key = os.environ.get("SENDGRID_API_KEY", "")
        r = req.get("https://api.sendgrid.com/v3/user/profile", headers={"Authorization": f"Bearer {key}"}, timeout=5)
        results["sendgrid"] = "✅ Connected" if r.status_code == 200 else f"❌ {r.status_code}"
    except Exception as e:
        results["sendgrid"] = f"❌ {str(e)[:80]}"

    try:
        sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        r = req.get(f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json", auth=(sid, token), timeout=5)
        results["twilio"] = "✅ Connected" if r.status_code == 200 else f"❌ {r.status_code}"
    except Exception as e:
        results["twilio"] = f"❌ {str(e)[:80]}"

    try:
        key = os.environ.get("VAPI_API_KEY", "")
        r = req.get("https://api.vapi.ai/phone-number", headers={"Authorization": f"Bearer {key}"}, timeout=5)
        results["vapi"] = "✅ Connected" if r.status_code == 200 else f"❌ {r.status_code}"
    except Exception as e:
        results["vapi"] = f"❌ {str(e)[:80]}"

    try:
        key = os.environ.get("HUBSPOT_API_KEY", "")
        r = req.get("https://api.hubapi.com/crm/v3/objects/contacts", headers={"Authorization": f"Bearer {key}"}, timeout=5)
        results["hubspot"] = "✅ Connected" if r.status_code == 200 else f"❌ {r.status_code}"
    except Exception as e:
        results["hubspot"] = f"❌ {str(e)[:80]}"

    all_ok = all("✅" in v for v in results.values())
    return {"all_systems_go": all_ok, "results": results}

# ── Leads ─────────────────────────────────────────────────────────────────────
@app.get("/leads/run", response_class=HTMLResponse)
async def run_leads(background_tasks: BackgroundTasks):
    def _run():
        try:
            from module1_lead_sourcing import LeadSourcingPipeline
            print("[Leads] Starting pipeline...")
            LeadSourcingPipeline().run(cities=["Mumbai", "Delhi", "Bangalore"], max_leads=100)
            print("[Leads] Pipeline complete!")
        except Exception as e:
            print(f"[Leads] Error: {e}")
    background_tasks.add_task(_run)
    return """
    <html><head><title>Sourcing Leads...</title>
    <meta http-equiv="refresh" content="60;url=/leads/list">
    <style>
      body{font-family:Arial;background:#0f1117;color:#e2e8f0;padding:40px;text-align:center;}
      .box{background:#1e2130;border-radius:14px;padding:40px;max-width:500px;margin:0 auto;}
      a{color:#a78bfa;}
      .spin{display:inline-block;font-size:3rem;animation:s 1s linear infinite;}
      @keyframes s{to{transform:rotate(360deg)}}
    </style></head>
    <body><div class="box">
      <div class="spin">⚙️</div>
      <h2 style="color:#a78bfa;margin-top:20px">Sourcing E-Commerce Leads...</h2>
      <p style="color:#64748b">Scanning Google Maps + Apollo.io + scoring SEO weakness.<br>Takes 3–5 minutes.</p>
      <p style="color:#64748b;margin-top:20px">
        Auto-redirecting to results in 60 seconds.<br>
        Or <a href="/leads/list">click here to check now</a>.
      </p>
    </div></body></html>
    """

@app.get("/leads/list")
async def list_leads(stage: str = None, limit: int = 50):
    try:
        from database import init_db, load_leads
        init_db()
        leads = load_leads(stage=stage, limit=limit)
        return {"total": len(leads), "leads": leads}
    except Exception as e:
        # Fallback to file
        try:
            with open("leads.json") as f:
                leads = json.load(f)
            if stage:
                leads = [l for l in leads if l.get("stage") == stage]
            return {"total": len(leads), "leads": leads[:limit]}
        except:
            return {"total": 0, "leads": [], "error": str(e)}

# ── Agent Chat ────────────────────────────────────────────────────────────────
@app.post("/agent/chat")
async def agent_chat(request: Request):
    body    = await request.json()
    lead    = body.get("lead", {"name": "Test", "website": "test.com", "pain_points": [], "stage": "new"})
    message = body.get("message", "Hello")
    channel = body.get("channel", "whatsapp")
    try:
        from module2_agent_brain import SalesAgentBrain
        result = SalesAgentBrain().chat(lead, message, channel=channel)
        return result
    except Exception as e:
        return {"error": str(e)}

# ── Vapi Webhook ──────────────────────────────────────────────────────────────
@app.post("/vapi/webhook")
async def vapi_webhook(request: Request):
    try:
        body = await request.json()
        event_type = body.get("message", {}).get("type", "")
        call_id    = body.get("message", {}).get("call", {}).get("id", "")
        print(f"[Vapi] {event_type} | {call_id}")
        if event_type == "function-call":
            from module3_voice_agent import handle_function_call
            fn   = body["message"].get("functionCall", {}).get("name", "")
            args = body["message"].get("functionCall", {}).get("parameters", {})
            result = await handle_function_call(fn, args, call_id)
            return JSONResponse({"result": result})
    except Exception as e:
        print(f"[Vapi] Error: {e}")
    return JSONResponse({"status": "ok"})

# ── Twilio Webhook ────────────────────────────────────────────────────────────
@app.post("/twilio/webhook")
async def twilio_webhook(request: Request):
    try:
        form        = await request.form()
        from_number = form.get("From", "").replace("whatsapp:", "")
        body        = form.get("Body", "")
        print(f"[WhatsApp] From: {from_number} | {body[:80]}")
        from module4_outreach import WhatsAppManager
        ai_reply = WhatsAppManager().handle_inbound_whatsapp(from_number, body)
        from twilio.twiml.messaging_response import MessagingResponse
        resp = MessagingResponse()
        resp.message(ai_reply)
        return HTMLResponse(content=str(resp), media_type="application/xml")
    except Exception as e:
        print(f"[Twilio] Error: {e}")
        return HTMLResponse(content="<Response/>", media_type="application/xml")
