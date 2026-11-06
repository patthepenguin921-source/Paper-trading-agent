## Your task this run: study (training, no trading)

This is a training session. Your owner has given you a curriculum written as if by
the head of a top Wall Street trading desk. Your job is to learn it thoroughly and
turn it into notes you will actually use on every future run.

1. Read every lesson in `analyst/library/curriculum/` (00 through 08), in order, in full.
2. Skim each dossier file in `analyst/library/stocks/`: read each sector primer in full,
   and enough of the individual entries to know which names are rate-sensitive, which are
   cyclical, which are defensive, which have squeeze risk, and what the key metric is for each group.
3. Using the brief, apply what you learned to the **current** market: what's the regime
   (lesson 01, with evidence from the overview table)? Which sectors lead and which lag? Which
   universe names fit which playbooks (lesson 05) right now?
4. Write `analyst/memory/knowledge.md`, your own condensed playbook. Write it in your own
   words, at most ~1,800 words, so it's cheap to reread every run. Include:
   - The core principles you'll live by (sizing tiers, exit rules, regime posture table).
   - A compact regime checklist and the ratio signals to check.
   - The playbooks as one-line rules each (entry / invalidation / exit).
   - Pre-trade checklist.
   - Sector cheat sheet: for each sector, the 2–3 drivers and the key metric.
   - "Things I must never do."
   If knowledge.md already exists, revise and improve it rather than starting over.
5. Update `analyst/memory/positions.md` with a **Watchlist** section: 5–10 names with the
   playbook each fits and what you're waiting for before acting.
6. Write `analyst/memory/journal/{{DATE}}-study.md`: what you studied, your regime call,
   and anything in the material you disagree with or want your owner to clarify.
7. Write `workspace/decisions.json` as `{"market_view": "...", "decisions": [], "journal": "..."}`.
   Study runs never trade.
