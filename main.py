import os
import json
import time
import threading
from datetime import datetime
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

# Global log buffer so UI can stream logs
log_buffer = []
pipeline_status = {"running": False, "progress": 0, "step": "idle", "total": 0}

def log(msg):
    timestamp = datetime.utcnow().strftime("%H:%M:%S")
    entry = "[" + timestamp + "] " + str(msg)
    print(entry)
    log_buffer.append(entry)
    if len(log_buffer) > 200:
        log_buffer.pop(0)

@asynccontextmanager
async def lifespan(app: FastAPI):
    log("AI Sales Agent started")
    yield

app = FastAPI(title="AI Sales Agent", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Main Dashboard ────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Sales Agent</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', sans-serif; background: #0f1117; color: #e2e8f0; min-height: 100vh; }
  .header { background: #1e2130; border-bottom: 1px solid #2d3148; padding: 16px 24px; display: flex; align-items: center; justify-content: space-between; }
  .header h1 { color: #a78bfa; font-size: 1.2rem; }
  .live-dot { width: 8px; height: 8px; background: #4ade80; border-radius: 50%; display: inline-block; margin-right: 6px; animation: pulse 1.5s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
  .grid { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 12px; padding: 20px; }
  .stat { background: #1e2130; border-radius: 12px; padding: 20px; border: 1px solid #2d3148; text-align: center; }
  .stat .num { font-size: 2.2rem; font-weight: 700; color: #a78bfa; }
  .stat .label { font-size: 0.78rem; color: #64748b; margin-top: 4px; }
  .panels { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding: 0 20px 20px; }
  .panel { background: #1e2130; border-radius: 12px; border: 1px solid #2d3148; overflow: hidden; }
  .panel-header { padding: 14px 18px; border-bottom: 1px solid #2d3148; display: flex; align-items: center; justify-content: space-between; }
  .panel-header h2 { font-size: 0.9rem; color: #a78bfa; }
  .panel-body { padding: 14px 18px; }
  .btn { padding: 8px 16px; border-radius: 8px; border: none; cursor: pointer; font-size: 0.82rem; font-weight: 600; transition: opacity 0.2s; }
  .btn:hover { opacity: 0.85; }
  .btn-primary { background: #6366f1; color: white; }
  .btn-green { background: #16a34a; color: white; }
  .btn-red { background: #dc2626; color: white; }
  .btn-ghost { background: #2d3148; color: #a78bfa; }
  .btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .log-box { background: #0f1117; border-radius: 8px; padding: 12px; height: 240px; overflow-y: auto; font-family: monospace; font-size: 0.75rem; color: #4ade80; border: 1px solid #2d3148; }
  .log-line { padding: 1px 0; border-bottom: 1px solid #0f1117; }
  .log-line.error { color: #f87171; }
  .log-line.success { color: #4ade80; }
  .log-line.info { color: #94a3b8; }
  .progress-wrap { margin: 10px 0; }
  .progress-bg { background: #0f1117; border-radius: 99px; height: 8px; }
  .progress-bar { height: 8px; border-radius: 99px; background: linear-gradient(90deg, #6366f1, #a78bfa); transition: width 0.5s; }
  .step-label { font-size: 0.78rem; color: #6366f1; margin-top: 4px; }
  .leads-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
  .leads-table th { background: #0f1117; padding: 8px 10px; text-align: left; color: #6366f1; position: sticky; top: 0; }
  .leads-table td { padding: 7px 10px; border-bottom: 1px solid #1a1f30; }
  .leads-table tr:hover td { background: #1a1f30; }
  .badge { padding: 2px 8px; border-radius: 20px; font-size: 0.68rem; font-weight: 600; }
  .badge-new { background: #1e3a5f; color: #60a5fa; }
  .badge-contacted { background: #1c1535; color: #c4b5fd; }
  .badge-pitched { background: #1a2e00; color: #86efac; }
  .badge-closed { background: #052e16; color: #4ade80; }
  .table-wrap { max-height: 320px; overflow-y: auto; }
  .chat-input { width: 100%; background: #0f1117; border: 1px solid #2d3148; border-radius: 8px; padding: 10px; color: #e2e8f0; font-size: 0.85rem; resize: none; }
  .chat-input:focus { outline: none; border-color: #6366f1; }
  .chat-box { background: #0f1117; border-radius: 8px; padding: 12px; height: 200px; overflow-y: auto; font-size: 0.82rem; margin-bottom: 10px; border: 1px solid #2d3148; }
  .msg { margin-bottom: 10px; }
  .msg .role { font-size: 0.7rem; color: #6366f1; margin-bottom: 2px; }
  .msg .text { color: #e2e8f0; line-height: 1.5; }
  .msg.ai .role { color: #a78bfa; }
  select { background: #0f1117; border: 1px solid #2d3148; color: #e2e8f0; border-radius: 6px; padding: 6px 10px; font-size: 0.8rem; }
  .full-panel { grid-column: 1 / -1; }
  .actions-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; }
  .tag { background: #1c1535; color: #c4b5fd; padding: 2px 8px; border-radius: 20px; font-size: 0.7rem; }
</style>
</head>
<body>

<div class="header">
  <h1>🤖 AI Sales Agent <span id="statusDot"><span class="live-dot"></span>Live</span></h1>
  <div style="font-size:0.8rem;color:#64748b" id="clock"></div>
</div>

<!-- Stats -->
<div class="grid">
  <div class="stat"><div class="num" id="statTotal">—</div><div class="label">Total Leads</div></div>
  <div class="stat"><div class="num" id="statNew">—</div><div class="label">New</div></div>
  <div class="stat"><div class="num" id="statContacted">—</div><div class="label">Contacted</div></div>
  <div class="stat"><div class="num" id="statClosed" style="color:#4ade80">—</div><div class="label">Closed 🎉</div></div>
</div>

<div class="panels">

  <!-- Pipeline Control -->
  <div class="panel">
    <div class="panel-header">
      <h2>⚙️ Pipeline Control</h2>
      <span id="pipelineStatus" style="font-size:0.75rem;color:#64748b">Idle</span>
    </div>
    <div class="panel-body">
      <div class="actions-row">
        <button class="btn" style="background:#f97316;color:white" onclick="runIndiamart()">🏭 Scrape IndiaMART</button>
        <button class="btn" style="background:#0ea5e9;color:white" onclick="enrichContacts()">🔍 Enrich Contacts</button>
        <button class="btn" style="background:#7c3aed;color:white" onclick="runOrchestrator()">🤖 Run Full Pipeline</button>
        <button class="btn" style="background:#16a34a;color:white" onclick="sendFollowups()">📨 Send Followups</button>
        <button class="btn btn-ghost" onclick="refreshAll()">↻ Refresh</button>
      </div>
      <div class="progress-wrap">
        <div class="progress-bg"><div class="progress-bar" id="progressBar" style="width:0%"></div></div>
        <div class="step-label" id="stepLabel">Ready</div>
      </div>
      <div class="log-box" id="logBox">
        <div class="log-line info">Waiting for activity...</div>
      </div>
    </div>
  </div>

  <!-- AI Brain Tester -->
  <div class="panel">
    <div class="panel-header">
      <h2>🧠 Test AI Brain</h2>
      <select id="channelSelect">
        <option value="call">📞 Call</option>
        <option value="whatsapp">💬 WhatsApp</option>
        <option value="email">📧 Email</option>
      </select>
    </div>
    <div class="panel-body">
      <div style="margin-bottom:8px;display:flex;gap:8px;align-items:center">
        <select id="leadSelect" style="flex:1" onchange="updateSelectedLead()">
          <option value="">— Select a lead —</option>
        </select>
        <button class="btn btn-ghost" onclick="loadLeadsIntoSelect()">↻</button>
      </div>
      <div id="leadTags" style="margin-bottom:8px;display:flex;gap:4px;flex-wrap:wrap"></div>
      <div class="chat-box" id="chatBox"></div>
      <div style="display:flex;gap:8px">
        <textarea class="chat-input" id="chatInput" rows="2" placeholder="Type a message as the prospect..."></textarea>
        <button class="btn btn-primary" onclick="sendChat()" style="align-self:flex-end">Send</button>
      </div>
    </div>
  </div>

  <!-- Leads Table -->
  <div class="panel full-panel">
    <div class="panel-header">
      <h2>📋 Leads Pipeline</h2>
      <div style="display:flex;gap:8px;align-items:center">
        <select id="stageFilter" onchange="filterLeads()">
          <option value="">All Stages</option>
          <option value="new">New</option>
          <option value="contacted">Contacted</option>
          <option value="pitched">Pitched</option>
          <option value="closed">Closed</option>
        </select>
        <span style="font-size:0.75rem;color:#64748b" id="leadsCount"></span>
      </div>
    </div>
    <div class="panel-body" style="padding:0">
      <div class="table-wrap">
        <table class="leads-table">
          <thead>
            <tr>
              <th>Name</th><th>Company</th><th>Phone</th><th>Email</th><th>City</th><th>Website</th><th>Stage</th><th>Pain Points</th><th>Action</th>
            </tr>
          </thead>
          <tbody id="leadsBody">
            <tr><td colspan="8" style="text-align:center;color:#64748b;padding:30px">
              Click "Load Seed Leads" or "Source Leads" to get started
            </td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

</div>

<script>
let allLeads = [];
let selectedLead = null;
let chatHistory = [];
let logPointer = 0;

// ── Clock ─────────────────────────────────────────────────────────────────────
function updateClock() {
  document.getElementById('clock').textContent = new Date().toUTCString().slice(0,25);
}
setInterval(updateClock, 1000);
updateClock();

// ── Stats ─────────────────────────────────────────────────────────────────────
async function loadStats() {
  try {
    const r = await fetch('/api/stats');
    const d = await r.json();
    document.getElementById('statTotal').textContent     = d.total || 0;
    document.getElementById('statNew').textContent       = d.new || 0;
    document.getElementById('statContacted').textContent = d.contacted || 0;
    document.getElementById('statClosed').textContent    = d.closed || 0;
  } catch(e) {}
}

// ── Leads ─────────────────────────────────────────────────────────────────────
async function loadLeads(stage='') {
  try {
    const url = '/leads/list' + (stage ? '?stage=' + stage : '');
    const r   = await fetch(url);
    const d   = await r.json();
    allLeads  = d.leads || [];
    renderLeads(allLeads);
    loadLeadsIntoSelect();
    document.getElementById('leadsCount').textContent = allLeads.length + ' leads';
  } catch(e) {}
}

function renderLeads(leads) {
  const body = document.getElementById('leadsBody');
  if (!leads.length) {
    body.innerHTML = '<tr><td colspan="9" style="text-align:center;color:#64748b;padding:30px">No leads yet — click Load Seed Leads or Scrape IndiaMART</td></tr>';
    return;
  }
  body.innerHTML = leads.map(l => {
    const badge = 'badge-' + (l.stage || 'new');
    const pain  = (l.pain_points || []).slice(0,2).map(p => '<span class="tag">' + p + '</span>').join(' ');

    // Phone — clickable WhatsApp link
    const rawPhone = (l.phone || '').toString().replace(/[^0-9]/g, '').slice(-10);
    const phone = rawPhone
      ? '<a href="https://wa.me/91' + rawPhone + '" target="_blank" style="color:#25d366;font-weight:600">📱 ' + rawPhone + '</a>'
      : '<span style="color:#4b5563">—</span>';

    // Email — mailto link
    const email = l.email
      ? '<a href="mailto:' + l.email + '" style="color:#a78bfa;font-size:0.75rem">' + l.email + '</a>'
      : '<span style="color:#4b5563">—</span>';

    // City — clean text only
    const city = (l.city || 'India').split(',')[0].trim();

    // Website — colour coded
    const site = l.website || '';
    const siteLabel = site.includes('wa.me') ? '💬 WhatsApp'
                    : site.replace('https://','').replace('http://','').split('/')[0] || '—';
    const siteColor = site.includes('wa.me') ? '#25d366'
                    : site.includes('indiamart') ? '#64748b' : '#a78bfa';
    const siteHtml = site
      ? '<a href="' + site + '" target="_blank" style="color:' + siteColor + ';font-size:0.75rem">' + siteLabel + '</a>'
      : '<span style="color:#4b5563">—</span>';

    return '<tr>' +
      '<td>' + (l.name || '—') + '</td>' +
      '<td>' + (l.company || '—') + '</td>' +
      '<td>' + phone + '</td>' +
      '<td>' + email + '</td>' +
      '<td>' + city + '</td>' +
      '<td>' + siteHtml + '</td>' +
      '<td><span class="badge ' + badge + '">' + (l.stage||'new') + '</span></td>' +
      '<td>' + pain + '</td>' +
      '<td><button class="btn btn-ghost" style="padding:4px 10px;font-size:0.72rem" onclick="selectLead(' + JSON.stringify(JSON.stringify(l)) + ')">Chat</button></td>' +
      '</tr>';
  }).join('');
}

function filterLeads() {
  const stage = document.getElementById('stageFilter').value;
  loadLeads(stage);
}

// ── Lead Select for Chat ──────────────────────────────────────────────────────
function loadLeadsIntoSelect() {
  const sel = document.getElementById('leadSelect');
  const cur = sel.value;
  sel.innerHTML = '<option value="">— Select a lead —</option>' +
    allLeads.map(l => '<option value="' + l.id + '">' + l.name + ' — ' + l.company + '</option>').join('');
  if (cur) sel.value = cur;
}

function updateSelectedLead() {
  const id = document.getElementById('leadSelect').value;
  selectedLead = allLeads.find(l => String(l.id) === String(id)) || null;
  chatHistory  = [];
  document.getElementById('chatBox').innerHTML = '';
  const tags = document.getElementById('leadTags');
  if (selectedLead) {
    const pain = (selectedLead.pain_points || []).map(p => '<span class="tag">' + p + '</span>').join(' ');
    tags.innerHTML = pain || '<span class="tag">no pain points tagged</span>';
  } else {
    tags.innerHTML = '';
  }
}

function selectLead(jsonStr) {
  const lead = JSON.parse(jsonStr);
  selectedLead = lead;
  chatHistory  = [];
  document.getElementById('chatBox').innerHTML = '';
  const opts = document.getElementById('leadSelect').options;
  for (let i = 0; i < opts.length; i++) {
    if (opts[i].text.includes(lead.name)) { opts[i].selected = true; break; }
  }
  const pain = (lead.pain_points || []).map(p => '<span class="tag">' + p + '</span>').join(' ');
  document.getElementById('leadTags').innerHTML = pain;
  document.getElementById('chatInput').focus();
}

// ── AI Chat ───────────────────────────────────────────────────────────────────
async function sendChat() {
  const input   = document.getElementById('chatInput');
  const message = input.value.trim();
  if (!message) return;
  if (!selectedLead) { alert('Select a lead first!'); return; }

  const channel = document.getElementById('channelSelect').value;
  input.value   = '';

  appendChat('prospect', message);

  try {
    const r = await fetch('/agent/chat', {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body:    JSON.stringify({ lead: selectedLead, message, channel })
    });
    const d = await r.json();
    appendChat('ai', d.response || d.error || 'No response');
    if (d.stage) selectedLead.stage = d.stage;
  } catch(e) {
    appendChat('ai', 'Error: ' + e.message);
  }
}

function appendChat(role, text) {
  const box  = document.getElementById('chatBox');
  const div  = document.createElement('div');
  div.className = 'msg ' + (role === 'ai' ? 'ai' : '');
  div.innerHTML = '<div class="role">' + (role === 'ai' ? '🤖 Aryan (AI)' : '👤 Prospect') + '</div>' +
                  '<div class="text">' + text + '</div>';
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

document.getElementById('chatInput').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
});

// ── Pipeline Actions ──────────────────────────────────────────────────────────
async function runIndiamart() {
  addLog('Starting IndiaMART scraper...', 'info');
  addLog('Categories: Clothing, Electronics, Food, Furniture', 'info');
  updateProgress(5, 'Scraping IndiaMART sellers...');
  document.getElementById('pipelineStatus').textContent = 'Running';
  try {
    const r = await fetch('/leads/indiamart');
    const d = await r.json();
    addLog('IndiaMART scraper started — scraping seller profiles...', 'info');
    pollLogs();
  } catch(e) {
    addLog('Error: ' + e.message, 'error');
  }
}

async function enrichContacts() {
  addLog('Starting contact enrichment...', 'info');
  addLog('Searching JustDial + Google for real phones and emails...', 'info');
  updateProgress(10, 'Enriching contacts...');
  try {
    await fetch('/leads/enrich?limit=30');
    addLog('Enrichment running — check logs for updates', 'success');
    pollLogs();
  } catch(e) { addLog('Error: ' + e.message, 'error'); }
}

async function runOrchestrator() {
  addLog('Starting full pipeline orchestrator...', 'info');
  addLog('Steps: Enrich contacts → Send WhatsApp → Track replies', 'info');
  updateProgress(5, 'Running orchestrator...');
  document.getElementById('pipelineStatus').textContent = 'Running';
  try {
    await fetch('/orchestrator/run?enrich=true&outreach=true');
    addLog('Orchestrator started — watch logs for progress', 'success');
    pollLogs();
  } catch(e) { addLog('Error: ' + e.message, 'error'); }
}

async function sendFollowups() {
  addLog('Sending follow-ups to contacted leads...', 'info');
  try {
    await fetch('/orchestrator/followups');
    addLog('Follow-ups queued — check logs', 'success');
    pollLogs();
  } catch(e) { addLog('Error: ' + e.message, 'error'); }
}

async function runInstagram() {
  addLog('Searching Google for Indian D2C brands...', 'info');
  addLog('Queries: Shopify India, WooCommerce India, fashion brands...', 'info');
  updateProgress(5, 'Scraping Instagram hashtags...');
  document.getElementById('pipelineStatus').textContent = 'Running';
  try {
    const r = await fetch('/leads/instagram');
    const d = await r.json();
    addLog('Scraper running — finds sites + extracts emails, phones, pain points', 'info');
    addLog('Watch logs for @username updates as brands are found...', 'info');
    pollLogs();
  } catch(e) {
    addLog('Error: ' + e.message, 'error');
  }
}



async function runPipeline() {
  addLog('Starting full pipeline...', 'info');
  updateProgress(5, 'Initializing...');
  document.getElementById('pipelineStatus').textContent = 'Running';
  try {
    await fetch('/leads/run');
    pollLogs();
  } catch(e) {
    addLog('Error: ' + e.message, 'error');
  }
}

async function pollLogs() {
  try {
    const r = await fetch('/api/logs?from=' + logPointer);
    const d = await r.json();
    for (const line of d.logs) {
      logPointer++;
      if (line.includes('Error') || line.includes('error')) addLog(line, 'error');
      else if (line.includes('Saved') || line.includes('Synced') || line.includes('Done')) addLog(line, 'success');
      else addLog(line, 'info');

      if (line.includes('STEP 1')) updateProgress(20, 'Step 1: Apollo Search...');
      if (line.includes('STEP 2')) updateProgress(40, 'Step 2: Loading stores...');
      if (line.includes('STEP 3')) updateProgress(60, 'Step 3: Seed leads...');
      if (line.includes('STEP 4')) updateProgress(75, 'Step 4: Tagging pain points...');
      if (line.includes('STEP 5')) updateProgress(90, 'Step 5: HubSpot sync...');
      if (line.includes('Synced')) { updateProgress(100, 'Complete!'); loadLeads(); loadStats(); document.getElementById('pipelineStatus').textContent = 'Idle'; }
    }
    if (!d.logs.some(l => l.includes('Synced') || l.includes('complete'))) {
      setTimeout(pollLogs, 2000);
    }
  } catch(e) {}
}

function addLog(msg, type='info') {
  const box  = document.getElementById('logBox');
  const line = document.createElement('div');
  line.className = 'log-line ' + type;
  line.textContent = msg;
  box.appendChild(line);
  box.scrollTop = box.scrollHeight;
  if (box.children.length === 1 && box.children[0].textContent === 'Waiting for activity...') {
    box.innerHTML = '';
    box.appendChild(line);
  }
}

function updateProgress(pct, label) {
  document.getElementById('progressBar').style.width = pct + '%';
  document.getElementById('stepLabel').textContent = label;
}

function refreshAll() { loadLeads(); loadStats(); }

// ── Auto-refresh ──────────────────────────────────────────────────────────────
loadLeads(); loadStats();
setInterval(() => { loadStats(); }, 10000);
</script>
</body>
</html>
""")


# ── API: Stats ────────────────────────────────────────────────────────────────
@app.get("/api/stats")
async def stats():
    try:
        from database import init_db, count_by_stage, load_leads
        init_db()
        counts = count_by_stage()
        total  = sum(counts.values())
        return {
            "total":     total,
            "new":       counts.get("new", 0),
            "contacted": counts.get("contacted", 0),
            "pitched":   counts.get("pitched", 0),
            "closed":    counts.get("closed", 0),
        }
    except Exception as e:
        return {"total": 0, "new": 0, "contacted": 0, "pitched": 0, "closed": 0, "error": str(e)}


# ── API: Logs (for live streaming to UI) ──────────────────────────────────────
@app.get("/api/logs")
async def get_logs(from_: int = 0):
    return {"logs": log_buffer[from_:], "total": len(log_buffer)}


# ── IndiaMART Scrape ─────────────────────────────────────────────────────────
@app.get("/leads/indiamart")
async def run_indiamart(background_tasks: BackgroundTasks, max_per_category: int = 25, clear: bool = False):
    def _run():
        try:
            from indiamart_scraper import IndiaMartLeadPipeline
            log("[IndiaMART] Starting scraper — Chemicals, Kanpur")
            log("[IndiaMART] Will clear old leads and fetch fresh data...")
            pipeline = IndiaMartLeadPipeline()
            leads = pipeline.run(max_per_category=max_per_category, clear_first=clear)
            has_phone = sum(1 for l in leads if l.phone)
            has_email = sum(1 for l in leads if l.email)
            log("[IndiaMART] Done! " + str(len(leads)) + " leads | " + str(has_phone) + " with phone | " + str(has_email) + " with email")
        except Exception as e:
            log("[IndiaMART] Error: " + str(e))
    background_tasks.add_task(_run)
    return {"status": "started", "message": "IndiaMART scraper running — Chemicals Kanpur"}


# ── Contact Enrichment ───────────────────────────────────────────────────────
@app.get("/leads/enrich")
async def enrich_contacts(background_tasks: BackgroundTasks, limit: int = 30):
    def _run():
        try:
            from contact_finder import BulkContactEnricher
            log("[Enrich] Starting contact enrichment for " + str(limit) + " leads...")
            log("[Enrich] Checking JustDial + Google + website scraping...")
            e = BulkContactEnricher()
            updated = e.run(limit=limit)
            log("[Enrich] Done! Updated " + str(updated) + " leads with real contacts")
        except Exception as e:
            log("[Enrich] Error: " + str(e))
    background_tasks.add_task(_run)
    return {"status": "started", "message": "Contact enrichment running"}


# ── Orchestrator ──────────────────────────────────────────────────────────────
@app.get("/orchestrator/run")
async def run_orchestrator(background_tasks: BackgroundTasks, scrape: bool = False, enrich: bool = True, outreach: bool = True):
    def _run():
        try:
            from module5_orchestrator import SalesOrchestrator
            log("[Orchestrator] Starting full pipeline...")
            orch    = SalesOrchestrator(log_fn=log)
            results = orch.run_full_pipeline(scrape_fresh=scrape, enrich=enrich, outreach=outreach)
            log("[Orchestrator] Complete: " + str(results))
        except Exception as e:
            log("[Orchestrator] Error: " + str(e))
    background_tasks.add_task(_run)
    return {"status": "started"}


@app.get("/orchestrator/summary")
async def pipeline_summary():
    try:
        from module5_orchestrator import SalesOrchestrator
        orch = SalesOrchestrator(log_fn=log)
        return orch.get_pipeline_summary()
    except Exception as e:
        return {"error": str(e)}


@app.get("/orchestrator/followups")
async def run_followups(background_tasks: BackgroundTasks):
    def _run():
        try:
            from module5_orchestrator import SalesOrchestrator
            orch = SalesOrchestrator(log_fn=log)
            sent = orch.run_followups()
            log("[Followup] Sent " + str(sent) + " follow-up messages")
        except Exception as e:
            log("[Followup] Error: " + str(e))
    background_tasks.add_task(_run)
    return {"status": "started"}


# ── Instagram Scrape ─────────────────────────────────────────────────────────
@app.get("/leads/instagram")
async def run_instagram(background_tasks: BackgroundTasks):
    def _run():
        try:
            from instagram_scraper import InstagramLeadPipeline
            log("[Instagram] Starting D2C brand scraper...")
            pipeline = InstagramLeadPipeline()
            leads = pipeline.run(max_leads=100)
            log("[Instagram] Done! Found " + str(len(leads)) + " brand leads")
        except Exception as e:
            log("[Instagram] Error: " + str(e))
    background_tasks.add_task(_run)
    return {"status": "started", "message": "Instagram scraper running in background"}


# ── Leads Seed ────────────────────────────────────────────────────────────────



# ── Leads Run ─────────────────────────────────────────────────────────────────
@app.get("/leads/run", response_class=HTMLResponse)
async def run_leads(background_tasks: BackgroundTasks):
    def _run():
        try:
            from module1_lead_sourcing import LeadSourcingPipeline
            log("Pipeline starting...")
            LeadSourcingPipeline().run(max_leads=100)
            log("Pipeline complete!")
        except Exception as e:
            log("Pipeline error: " + str(e))
    background_tasks.add_task(_run)
    return HTMLResponse("""<html><body style="background:#0f1117;color:#a78bfa;font-family:Arial;padding:40px;text-align:center">
        <h2>Pipeline started!</h2><p style="color:#64748b">Go back to <a href="/" style="color:#a78bfa">dashboard</a> to watch live progress.</p>
        </body></html>""")


# ── Clear non-IndiaMART leads ────────────────────────────────────────────────
@app.get("/leads/clear-old")
async def clear_old():
    try:
        from database import get_conn
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM leads WHERE source != 'indiamart'")
        conn.commit()
        deleted = cur.rowcount
        cur.close()
        conn.close()
        log("Cleared " + str(deleted) + " non-IndiaMART leads")
        return {"status": "ok", "deleted": deleted}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ── Leads List ────────────────────────────────────────────────────────────────
@app.get("/leads/list")
async def list_leads(stage: str = None, limit: int = 200):
    try:
        from database import init_db, load_leads
        init_db()
        leads = load_leads(stage=stage, limit=limit)
        return {"total": len(leads), "leads": leads}
    except Exception as e:
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
        return {"error": str(e), "response": "AI error: " + str(e)}


# ── Test Keys ─────────────────────────────────────────────────────────────────
@app.get("/test-keys")
async def test_keys():
    import requests as req
    results = {}
    try:
        import openai
        openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY")).models.list()
        results["openai"] = "Connected"
    except Exception as e:
        results["openai"] = "Error: " + str(e)[:60]
    return {"results": results}


# ── Vapi Webhook ──────────────────────────────────────────────────────────────
@app.post("/vapi/webhook")
async def vapi_webhook(request: Request):
    try:
        body       = await request.json()
        event_type = body.get("message", {}).get("type", "")
        call_id    = body.get("message", {}).get("call", {}).get("id", "")
        log("[Vapi] " + event_type + " | " + call_id)
        if event_type == "function-call":
            from module3_voice_agent import handle_function_call
            fn   = body["message"].get("functionCall", {}).get("name", "")
            args = body["message"].get("functionCall", {}).get("parameters", {})
            result = await handle_function_call(fn, args, call_id)
            return JSONResponse({"result": result})
    except Exception as e:
        log("[Vapi] Error: " + str(e))
    return JSONResponse({"status": "ok"})


# ── Twilio Webhook ────────────────────────────────────────────────────────────
@app.post("/twilio/webhook")
async def twilio_webhook(request: Request):
    try:
        form        = await request.form()
        from_number = form.get("From", "").replace("whatsapp:", "")
        body        = form.get("Body", "")
        log("[WhatsApp] From: " + from_number)
        from module4_outreach import WhatsAppManager
        ai_reply = WhatsAppManager().handle_inbound_whatsapp(from_number, body)
        from twilio.twiml.messaging_response import MessagingResponse
        resp = MessagingResponse()
        resp.message(ai_reply)
        return HTMLResponse(content=str(resp), media_type="application/xml")
    except Exception as e:
        log("[Twilio] Error: " + str(e))
        return HTMLResponse(content="<Response/>", media_type="application/xml")
