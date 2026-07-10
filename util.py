"""
Small helpers shared across ai_agent.py and the modules it split into
(backends.py, news.py, risk.py, store.py) — kept separate to avoid import
cycles (everything can depend on util; util depends on nothing here).
"""
import re

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
