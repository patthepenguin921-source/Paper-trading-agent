"""
Weekend-only entry point: sweeps Eris' crypto positions for the per-position
stop-loss cap without waiting for main.py's equity-market-hours gate. See
ai_agent.run_weekend_crypto_backstop() and
.github/workflows/weekend_crypto_backstop.yml.
"""
import ai_agent

if __name__ == "__main__":
    ai_agent.run_weekend_crypto_backstop()
