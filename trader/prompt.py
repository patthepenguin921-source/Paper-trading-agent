"""
Renders the analyst prompt for a given mode.

    python -m trader.prompt trade|review > workspace/prompt.md
"""
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent


def render(mode: str, now: datetime | None = None) -> str:
    if mode not in ("trade", "review"):
        raise SystemExit("mode must be 'trade' or 'review'")
    now = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo("America/New_York"))
    slot = "am" if now.hour < 13 else "pm"
    text = (ROOT / "analyst/PROMPT.md").read_text()
    text = text.replace("{{MODE_INSTRUCTIONS}}", (ROOT / f"analyst/modes/{mode}.md").read_text())
    label = "trading" if mode == "trade" else "weekly review"
    return (text.replace("{{MODE}}", label)
                .replace("{{DATE}}", f"{now:%Y-%m-%d}")
                .replace("{{SLOT}}", slot))


if __name__ == "__main__":
    print(render(sys.argv[1] if len(sys.argv) > 1 else "trade"))
