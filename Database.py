import os
import json
import psycopg2
import psycopg2.extras
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "")


def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def init_db():
    """Create leads table if it doesn't exist."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id SERIAL PRIMARY KEY,
                    name TEXT,
                    website TEXT,
                    phone TEXT,
                    email TEXT,
                    city TEXT,
                    source TEXT,
                    linkedin_url TEXT DEFAULT '',
                    job_title TEXT DEFAULT '',
                    company TEXT DEFAULT '',
                    seo_score INTEGER,
                    pagespeed_score INTEGER,
                    pain_points TEXT DEFAULT '[]',
                    stage TEXT DEFAULT 'new',
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
        conn.commit()
    print("[DB] Table ready")


def save_leads(leads):
    """Save list of Lead dataclass objects to PostgreSQL."""
    if not leads:
        return 0
    with get_conn() as conn:
        with conn.cursor() as cur:
            saved = 0
            for lead in leads:
                d = lead if isinstance(lead, dict) else lead.__dict__
                # Upsert by website+name
                cur.execute("""
                    INSERT INTO leads
                        (name, website, phone, email, city, source,
                         linkedin_url, job_title, company,
                         seo_score, pagespeed_score, pain_points,
                         stage, created_at, updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT DO NOTHING
                """, (
                    d.get("name",""),
                    d.get("website",""),
                    d.get("phone",""),
                    d.get("email",""),
                    d.get("city",""),
                    d.get("source",""),
                    d.get("linkedin_url",""),
                    d.get("job_title",""),
                    d.get("company",""),
                    d.get("seo_score"),
                    d.get("pagespeed_score"),
                    json.dumps(d.get("pain_points") or []),
                    d.get("stage","new"),
                    d.get("created_at", datetime.utcnow().isoformat()),
                    datetime.utcnow().isoformat()
                ))
                saved += 1
        conn.commit()
    print("[DB] Saved " + str(saved) + " leads")
    return saved


def load_leads(stage=None, limit=200):
    """Load leads from PostgreSQL."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if stage:
                cur.execute("SELECT * FROM leads WHERE stage=%s ORDER BY id DESC LIMIT %s", (stage, limit))
            else:
                cur.execute("SELECT * FROM leads ORDER BY id DESC LIMIT %s", (limit,))
            rows = cur.fetchall()
            leads = []
            for r in rows:
                r = dict(r)
                try:
                    r["pain_points"] = json.loads(r.get("pain_points") or "[]")
                except:
                    r["pain_points"] = []
                leads.append(r)
            return leads


def update_lead_stage(lead_id, stage):
    """Update a lead's stage."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE leads SET stage=%s, updated_at=%s WHERE id=%s",
                (stage, datetime.utcnow().isoformat(), lead_id)
            )
        conn.commit()


def count_by_stage():
    """Get count of leads per stage."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT stage, COUNT(*) as cnt FROM leads GROUP BY stage")
            return {row[0]: row[1] for row in cur.fetchall()}
