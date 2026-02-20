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
    # Add followers column to existing tables that predate this schema
    try:
        cur.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS followers INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        conn.rollback()
    cur.close()
    conn.close()
    print("[DB] Table ready")


def save_leads(leads):
    if not leads:
        return 0
    saved = 0
    errors = 0
    for lead in leads:
        # Fresh connection per row — avoids aborted transaction poisoning
        conn = get_conn()
        cur = conn.cursor()
        try:
            d = lead if isinstance(lead, dict) else lead.__dict__

            raw_pain = d.get("pain_points") or []
            if isinstance(raw_pain, str):
                try:
                    raw_pain = json.loads(raw_pain)
                except Exception:
                    raw_pain = []
            pain_json = json.dumps([str(p) for p in raw_pain])

            cur.execute("""
                INSERT INTO leads
                (name, website, phone, email, city, source,
                 linkedin_url, job_title, company,
                 seo_score, pagespeed_score, pain_points,
                 followers, stage, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s)
            """, (
                str(d.get("name") or "")[:200],
                str(d.get("website") or "")[:500],
                str(d.get("phone") or "")[:50],
                str(d.get("email") or "")[:200],
                str(d.get("city") or "")[:100],
                str(d.get("source") or "")[:50],
                str(d.get("linkedin_url") or "")[:500],
                str(d.get("job_title") or "")[:200],
                str(d.get("company") or "")[:200],
                d.get("seo_score") or None,
                d.get("pagespeed_score") or None,
                pain_json,
                int(d.get("followers") or 0),
                str(d.get("stage") or "new"),
                str(d.get("created_at") or datetime.utcnow().isoformat()),
                datetime.utcnow().isoformat(),
            ))
            conn.commit()
            saved += 1
        except Exception as e:
            conn.rollback()
            errors += 1
            print("[DB] Row error: " + repr(e)[:150])
        finally:
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
