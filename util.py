"""
Small helpers shared across ai_agent.py and the modules it split into
(backends.py, news.py, risk.py, store.py, snapshot.py) — kept separate to
avoid import cycles (everything can depend on util; util depends on
nothing here).
"""
import re
import time

import requests

_KEY_PARAM_RE = re.compile(r"([?&]key=)[^&\s]+")



def _safe_str(e: Exception) -> str:
    """
    str(exception) for a failed Gemini request includes the full request URL
    — which includes the API key as a `?key=...` query param. GitHub Actions
    auto-masks secrets in its own log viewer, but that masking doesn't apply
    to data this code separately ships off to Supabase (and from there, the
    public dashboard). Always scrub before logging/storing any exception
    text so a key can't end up sitting in plaintext somewhere masking can't
    reach.
    """
    return _KEY_PARAM_RE.sub(r"\1***", str(e))


def request_with_retry(method, url, *, retries: int = 2, backoff: float = 2.0, **kwargs):
    """
    Runs a requests call (method is e.g. requests.post/requests.delete) and
    retries on transient timeouts/connection errors with a short linear
    backoff before giving up.

    Supabase occasionally takes longer than the per-call timeout to respond
    (observed repeatedly as requests.exceptions.ReadTimeout on the
    once-a-minute snapshot workflows), which previously failed the whole
    run/job on a single slow response. Every call site this wraps is an
    idempotent upsert (Prefer: resolution=merge-duplicates) or a filtered
    delete, so re-sending on failure is always safe.
    """
    last_exc = None
    for attempt in range(retries + 1):
        try:
            resp = method(url, **kwargs)
            resp.raise_for_status()
            return resp
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(backoff * (attempt + 1))
    raise last_exc
