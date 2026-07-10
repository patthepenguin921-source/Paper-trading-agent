"""
Raw model-backend calls: Groq (llama-3.3-70b) and Gemini, with API-key
rotation/fallback on rate limits. ai_agent._call_model decides which of
these to use per agent and builds the prompt; this module only knows how
to actually make the HTTP call and parse the response.
"""
import os
import time as time_module

import requests

import config
from util import _safe_str, _KEY_PARAM_RE

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_API_KEY_2 = os.environ.get("GEMINI_API_KEY_2", "")
GEMINI_KEYS = [k for k in (GEMINI_API_KEY, GEMINI_API_KEY_2) if k]
GEMINI_KEY_NAMES = ["GEMINI_API_KEY", "GEMINI_API_KEY_2"][: len(GEMINI_KEYS)]

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_API_KEY_2 = os.environ.get("GROQ_API_KEY_2", "")
GROQ_KEYS = [k for k in (GROQ_API_KEY, GROQ_API_KEY_2) if k]
GROQ_KEY_NAMES = ["GROQ_API_KEY", "GROQ_API_KEY_2"][: len(GROQ_KEYS)]


def _groq_generate(system_prompt: str, user_message: str, *,
                    json_mode=True, max_output_tokens=2000) -> str:
    """
    Call Groq's inference API (api.groq.com) with key failover between
    GROQ_API_KEY and GROQ_API_KEY_2.

    Serves two roles:
    - Primary backend for Hermes (ai_backend == "groq"), using
      llama-3.3-70b-versatile as the decision model.
    - Fallback for Gemini-backed agents (Plutus/Helios) when all Gemini
      keys are exhausted or Gemini is returning errors.

    Groq's OpenAI-compatible API means no code changes between the two
    roles — same function, same endpoint, same response shape.
    """
    # Use the agent's configured Groq model when running as Hermes (primary
    # backend). Fall back to llama-3.3-70b-versatile for the Gemini-fallback
    # case where Plutus/Helios hit quota — that path doesn't set a groq_model.
    model = config.AGENT.get("groq_model", "llama-3.3-70b-versatile")
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": max_output_tokens,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    last_error = None
    n_keys = len(GROQ_KEYS)
    for i, key in enumerate(GROQ_KEYS):
        key_name = GROQ_KEY_NAMES[i]
        try:
            print(f"Calling {key_name}")
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=60,
            )
            if resp.status_code == 429 and i < n_keys - 1:
                print(f"Groq key #{i + 1} hit a rate/quota limit (429), trying next key...")
                continue
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as e:
            last_error = e
            if i < n_keys - 1:
                print(f"Groq key #{i + 1} failed ({e}), trying next key...")
    raise last_error or RuntimeError("No Groq API keys configured")


def _gemini_generate(system_prompt: str, user_message: str, *, tools=None,
                      json_mode=True, max_output_tokens=2000) -> str:
    """
    Shared Gemini call with key failover. Returns the raw text of the first
    candidate's first part — callers decide whether/how to parse it.

    Note: Gemini 2.5 models reject combining a tool (like google_search) with
    responseMimeType="application/json" in the same call (400 INVALID_ARGUMENT,
    "Function calling with a response mime type... is unsupported"). So
    json_mode and tools are mutually exclusive here by construction — the news
    research call uses tools with json_mode=False, the decision call uses
    json_mode=True with no tools, and their outputs are stitched together by
    the caller instead.
    """
    # Deferred import: store.py imports backends._active_model_name at top
    # level, so a top-level "import store" here would be circular. By the
    # time this function actually runs, both modules are already loaded.
    from store import _notify

    generation_config = {"maxOutputTokens": max_output_tokens}
    if json_mode:
        generation_config["responseMimeType"] = "application/json"

    body = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_message}]}],
        "generationConfig": generation_config,
    }
    if tools:
        body["tools"] = tools

    last_error = None
    n_keys = len(GEMINI_KEYS)
    for i, key in enumerate(GEMINI_KEYS):
        key_name = GEMINI_KEY_NAMES[i]
        is_last_key = i == n_keys - 1
        rate_limit_attempts = 3 if is_last_key else 1
        for attempt in range(rate_limit_attempts):
            try:
                print(f"Calling {key_name} (attempt {attempt + 1})" if attempt > 0 else f"Calling {key_name}")
                resp = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{config.AGENT['gemini_model']}:generateContent",
                    params={"key": key},
                    headers={"content-type": "application/json"},
                    json=body,
                    timeout=60,
                )
                # 429 (rate/quota limit) and 5xx (transient server-side
                # errors — e.g. 503 Service Unavailable, which Gemini returns
                # on brief overload and which used to fall straight through
                # to an immediate Groq fallback with zero retries) both get
                # the same retry-with-backoff treatment on the last key
                # before giving up on Gemini entirely. Groq is meant to be a
                # last resort (it's also a weaker model and has its own
                # payload-size limits — see _groq_generate), not something a
                # single transient Gemini hiccup should route to.
                transient = resp.status_code == 429 or resp.status_code >= 500
                if transient:
                    safe_body = _KEY_PARAM_RE.sub(r"\1***", resp.text)[:500]
                    print(f"Gemini {resp.status_code} response body: {safe_body}")
                    if not is_last_key:
                        print(f"Gemini key #{i + 1} hit a transient error ({resp.status_code}), trying next key...")
                        break
                    quota_exhausted = (
                        resp.status_code == 429
                        and "RESOURCE_EXHAUSTED" in resp.text
                        and "free_tier_requests" in resp.text
                    )
                    if quota_exhausted:
                        print(f"Gemini key #{i + 1}: daily free-tier quota exhausted — not retrying, won't clear within seconds.")
                        _notify(
                            "API quota exhausted",
                            f"{GEMINI_KEY_NAMES[i]} hit the daily free-tier limit and won't recover until midnight PT. "
                            f"{'Trying next key.' if not is_last_key else 'No more Gemini keys — falling back to Groq.'}"
                        )
                    elif attempt < rate_limit_attempts - 1:
                        wait = 8 * (attempt + 1)
                        print(
                            f"Gemini key #{i + 1} hit a transient error ({resp.status_code}), no fallback key "
                            f"left — waiting {wait}s and retrying ({attempt + 1}/{rate_limit_attempts - 1})..."
                        )
                        time_module.sleep(wait)
                        continue
                resp.raise_for_status()
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except requests.exceptions.RequestException as e:
                last_error = e
                if not is_last_key:
                    print(f"Gemini key #{i + 1} failed ({e}), trying next key...")
                    break
                if tools is None and GROQ_KEYS:
                    print(f"All Gemini keys failed ({e}), falling back to Groq...")
                    _notify("Falling back to Groq", f"All Gemini keys failed ({_safe_str(e)[:120]}). This run will use Groq (llama-3.3-70b).")
                    return _groq_generate(
                        system_prompt, user_message,
                        json_mode=json_mode, max_output_tokens=max_output_tokens,
                    )
                raise
    if tools is None and GROQ_KEYS:
        print(f"All Gemini keys failed ({last_error}), falling back to Groq...")
        _notify("Falling back to Groq", f"All Gemini keys failed ({_safe_str(last_error)[:120]}). This run will use Groq (llama-3.3-70b).")
        return _groq_generate(
            system_prompt, user_message,
            json_mode=json_mode, max_output_tokens=max_output_tokens,
        )
    raise last_error or RuntimeError("No Gemini API keys configured")


def _active_model_name() -> str:
    """Returns a human-readable model name for logging."""
    backend = config.AGENT.get("ai_backend", "gemini")
    if backend == "groq":
        return config.AGENT.get("groq_model", "llama-3.3-70b-versatile")
    return config.AGENT.get("gemini_model", "unknown")
