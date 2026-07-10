"""
ai_agent.py/alpaca_client.py/config.py all read required credentials from
os.environ at import time (see ai_agent.py's "API keys" section) — set
harmless dummy values before anything under test imports those modules, so
the suite never needs real Alpaca/Supabase/Gemini credentials and never
makes a real network call just by importing.
"""
import os

os.environ.setdefault("ALPACA_API_KEY", "test-alpaca-key")
os.environ.setdefault("ALPACA_SECRET_KEY", "test-alpaca-secret")
os.environ.setdefault("SUPABASE_URL", "https://example.invalid")
os.environ.setdefault("SUPABASE_KEY", "test-supabase-key")
os.environ.setdefault("AGENT_ID", "plutus")
