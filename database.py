import os
import json
import psycopg2
import psycopg2.extras
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "")


def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id SERIAL PRIMARY KEY,
            name TEXT DEFAULT '',
            website TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            email TEXT DEFAULT '',
            city TEXT DEFAULT '',
            source TEXT DEFAULT '',
            linkedin_url TEXT DEFAULT '',
            job_title TEXT DEFAULT '',
            company TEXT DEFAULT '',
            seo_score INTEGER,
            pagespeed_score INTEGER,
            pain_points TEXT DEFAULT '[]',
            followers INTEGER DEFAULT 0,
            stage TEXT DEFAULT 'new',
            created_at TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("[DB] Table ready")


def save_leads(leads):
    if not leads:
        return 0
    conn = get_conn()
    cur = conn.cursor()
    saved = 0
    errors = 0
    for lead in leads:
        d = lead if isinstance(lead, dict) else lead.__dict__
        try:
            # Serialize pain_points safely
            raw_pain = d.get("pain_points") or []
            if isinstance(raw_pain, str):
                try:
                    raw_pain = json.loads(raw_pain)
                except Exception:
                    raw_pain = []
            pain_json = json.dumps([str(p) for p in raw_pain])

            name        = str(d.get("name") or "")[:200]
            website     = str(d.get("website") or "")[:500]
            phone       = str(d.get("phone") or "")[:50]
            email       = str(d.get("email") or "")[:200]
            city        = str(d.get("city") or "")[:100]
            source      = str(d.get("source") or "")[:50]
            linkedin    = str(d.get("linkedin_url") or "")[:500]
            job_title   = str(d.get("job_title") or "")[:200]
            company     = str(d.get("company") or "")[:200]
            seo_score   = d.get("seo_score") or None
            page_score  = d.get("pagespeed_score") or None
            followers   = int(d.get("followers") or 0)
            stage       = str(d.get("stage") or "new")
            created_at  = str(d.get("created_at") or datetime.utcnow().isoformat())
            updated_at  = datetime.utcnow().isoformat()

            sql = (
                "INSERT INTO leads "
                "(name, website, phone, email, city, source, "
                "linkedin_url, job_title, company, "
                "seo_score, pagespeed_score, pain_points, "
                "followers, stage, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, "
                "%s, %s, %s, "
                "%s, %s, %s, "
                "%s, %s, %s, %s)"
            )
            args = (
                name, website, phone, email, city, source,
                linkedin, job_title, company,
                seo_score, page_score, pain_json,
                followers, stage, created_at, updated_at
            )
            print("[DB] Inserting: " + name + " | args count: " + str(len(args)))
            cur.execute(sql, args)
            saved += 1
        except Exception as e:
            errors += 1
            print("[DB] Row error full: " + repr(e))
    conn.commit()
    cur.close()
    conn.close()
    print("[DB] Saved " + str(saved) + " | Errors " + str(errors))
    return saved


def load_leads(stage=None, limit=200):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if stage:
        cur.execute("SELECT * FROM leads WHERE stage=%s ORDER BY id DESC LIMIT %s", (stage, limit))
    else:
        cur.execute("SELECT * FROM leads ORDER BY id DESC LIMIT %s", (limit,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    leads = []
    for r in rows:
        r = dict(r)
        try:
            r["pain_points"] = json.loads(r.get("pain_points") or "[]")
        except Exception:
            r["pain_points"] = []
        leads.append(r)
    return leads


def update_lead_stage(lead_id, stage):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE leads SET stage=%s, updated_at=%s WHERE id=%s",
        (stage, datetime.utcnow().isoformat(), lead_id)
    )
    conn.commit()
    cur.close()
    conn.close()


def count_by_stage():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT stage, COUNT(*) FROM leads GROUP BY stage")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {row[0]: row[1] for row in rows}
