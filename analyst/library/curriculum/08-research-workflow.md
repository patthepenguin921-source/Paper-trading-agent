# 08: Research workflow: getting the most out of a limited run

You have roughly 60 steps per run and a usage budget shared with your owner. Every
file read and web search costs steps. Research like a PM with a plane to catch.

## The routine
1. **Brief first** (`workspace/brief.md`): account, positions, fills, performance, market
   overview, movers, universe stats, news. This is your morning meeting. 1–2 steps.
2. **Book review:** for each position, compare current price vs entry vs thesis in
   `memory/positions.md`, and scan held-position news in the brief. Only open a dossier or
   search the web for a holding if something changed (big move, news, earnings coming).
3. **Regime call:** use lesson 01's ratios on the market overview table. One paragraph.
4. **Idea generation**, cheapest to most expensive:
   - Scan the universe table: strongest momentum in leading sectors (longs), weakest in
     lagging sectors (shorts), names near highs with improving trends, oversold quality in uptrends.
   - Scan movers/news for earnings gaps (playbook A) and broken stories (playbook D).
   - Your watchlist in `positions.md`.
5. **Due diligence** on the best 2–3 candidates only:
   - Dossier: open the relevant `library/stocks/*.md` and Grep for `### TICKER` to jump to the entry.
   - Price history: read the CSV's last ~60–120 rows (Grep or Read with offset) to see structure,
     earnings gaps and volume.
   - One or two targeted web searches: "[TICKER] earnings guidance [month year]",
     "[TICKER] analyst estimates revisions", "[TICKER] news today".
   - Run the pre-trade checklist (lesson 05).
6. **Decide and write** decisions.json, positions.md, journal.

## Efficient tool use
- **Grep before Read.** `Grep "### NVDA" analyst/library/stocks/` finds the entry, then Read
  with an offset to get just that section.
- For CSVs, read the tail (most recent rows) rather than the whole file.
- Prefer one high-quality source (company press release, SEC filing, major financial news) over
  five low-quality ones. Note the source and date in your journal.
- Never trust a single unverified web claim for a big position, especially exact numbers.
- If you're running low on steps, stop researching and write your decisions. A run
  without decisions.json is a wasted run.

## Building your own knowledge over time
- When you learn something durable about a company (how it reacts to earnings, a key
  metric, management credibility), add a short "Analyst notes" line to your memory
  (`memory/lessons.md` if general, or the watchlist/positions notes if specific).
- Keep `library/INDEX.md` updated when you study new documents the owner adds.
- In the weekly review, look across the dossiers of your holdings and watchlist for things
  that have gone stale, and note corrections in your memory. Don't edit the dossiers
  themselves; the owner maintains those.
