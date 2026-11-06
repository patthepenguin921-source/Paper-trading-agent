"""
Supabase logging (tables pt_runs, pt_decisions, pt_snapshots; see
supabase/schema.sql). Logging is best effort: a Supabase outage prints a
warning but never blocks or undoes a trade.
"""
import os

import requests

URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
KEY = os.environ.get("SUPABASE_KEY", "")


def _enabled() -> bool:
    return bool(URL and KEY)


def _headers(prefer: str = "return=representation") -> dict:
    return {"apikey": KEY, "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json", "Prefer": prefer}


def insert(table: str, rows: dict | list[dict]) -> list[dict]:
    if not _enabled():
        print(f"[store] SUPABASE_URL/KEY not set; skipping insert into {table}")
        return []
    for attempt in range(3):
        try:
            r = requests.post(f"{URL}/rest/v1/{table}", headers=_headers(), json=rows, timeout=20)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            print(f"[store] insert into {table} failed (attempt {attempt + 1}): {e}")
    return []


def select(table: str, params: dict) -> list[dict]:
    if not _enabled():
        return []
    try:
        r = requests.get(f"{URL}/rest/v1/{table}", headers=_headers(), params=params, timeout=20)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        print(f"[store] select from {table} failed: {e}")
        return []


def log_run(agent_id: str, **fields) -> int | None:
    rows = insert("pt_runs", {"agent_id": agent_id, **fields})
    return rows[0]["id"] if rows else None


def log_decisions(run_id: int | None, agent_id: str, results: list[dict]):
    if not results:
        return
    insert("pt_decisions", [{"run_id": run_id, "agent_id": agent_id, **r} for r in results])
