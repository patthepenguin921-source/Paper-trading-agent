## Your task this run: decide trades

1. Review every open position against its thesis in `positions.md`. Is the thesis
   intact, played out, or broken? Act on it: hold, trim (sell/cover with a
   `fraction`), or close.
2. Look for new opportunities. Prefer a few high-conviction ideas over many small
   bets. Doing nothing is a valid decision when nothing is compelling.
3. Write `workspace/decisions.json` with exactly this shape (valid JSON, no comments):

```json
{
  "market_view": "2-4 sentences on the market backdrop and how you're positioned.",
  "decisions": [
    {"symbol": "MSFT", "action": "buy", "size_pct": 6, "confidence": 0.7,
     "thesis": "Why, with the specific evidence.", "exit_plan": "Target / stop / what would change your mind."},
    {"symbol": "XOM", "action": "sell", "fraction": 1.0, "confidence": 0.8,
     "thesis": "Why exiting."}
  ],
  "journal": "A short summary of this run's reasoning (it's shown on the dashboard)."
}
```
   - `action`: `buy` (open/add long), `sell` (reduce/close long), `short` (open/add
     short), `cover` (reduce/close short).
   - `size_pct`: % of total equity for the new money (buy/short only).
   - `fraction`: 0-1 share of the position to close (sell/cover only; default 1).
   - `confidence`: 0-1, calibrated. 0.5 is a coin flip.
   - Omit positions you're simply holding. An empty `decisions` list is fine.
4. Update memory:
   - `analyst/memory/positions.md`: one section per position you'll hold after this
     run (thesis, entry date/price, target, stop, what would invalidate it). Remove
     closed ones.
   - Create `analyst/memory/journal/{{DATE}}-{{SLOT}}.md` with what you looked at,
     what you decided and why, and what you passed on.
   - Add to `analyst/memory/lessons.md` only when a closed trade or an observation
     taught you something genuinely new. Keep it a curated list, not a log.
