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
    cur.execute(
        "CREATE TABLE IF NOT EXISTS leads ("
        "id SERIAL PRIMARY KEY,"
        "name TEXT,"
        "website TEXT,"
        "phone TEXT,"
        "email TEXT,"
        "city TEXT,"
        "source TEXT,"
        "linkedin_url TEXT DEFAULT '',"
        "job_title TEXT DEFAULT '',"
        "company TEXT DEFAULT '',"
        "seo_score INTEGER,"
        "pagespeed_score INTEGER,"
        "pain_points TEXT DEFAULT '[]',"
        "followers INTEGER DEFAULT 0,""stage TEXT DEFAULT 'new',"
        "created_at TEXT,"
        "updated_at TEXT"
        ")"
    )
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
    for lead in leads:
        if isinstance(lead, dict):
            d = lead
        else:
            d = lead.__dict__
        try:
            cur.execute(
                "INSERT INTO leads "
                "(name,website,phone,email,city,source,linkedin_url,job_title,company,"
                "seo_score,pagespeed_score,pain_points,stage,created_at,updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    str(d.get("name") or ""),
                    str(d.get("website") or ""),
                    str(d.get("phone") or ""),
                    str(d.get("email") or ""),
                    str(d.get("city") or ""),
                    str(d.get("source") or ""),
                    str(d.get("linkedin_url") or ""),
                    str(d.get("job_title") or ""),
                    str(d.get("company") or ""),
                    d.get("seo_score"),
                    d.get("pagespeed_score"),
                    json.dumps(d.get("pain_points") or []),
                    int(d.get("followers") or 0),
                    str(d.get("stage") or "new"),
                    str(d.get("created_at") or datetime.utcnow().isoformat()),
                    datetime.utcnow().isoformat()
                )
            )
            saved += 1
        except Exception as e:
            print("[DB] Row error: " + str(e))
    conn.commit()
    cur.close()
    conn.close()
    print("[DB] Saved " + str(saved) + " leads")
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
