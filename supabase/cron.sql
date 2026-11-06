-- Scheduling via Supabase pg_cron (much more punctual than GitHub's own cron).
-- Reuses public.trigger_github_workflow(), which dispatches a workflow on
-- `main` with inputs {source: 'schedule'} using the github_dispatch_token
-- stored in Supabase Vault.
--
-- Apply AFTER the new workflows are merged to main.

-- 1) Retire the four old agents (trade + per-minute snapshot triggers).
select cron.unschedule(jobname) from cron.job
where jobname in ('plutus-trigger', 'helios-trigger', 'hermes-trigger', 'eris-trigger',
                  'plutus-snapshot-trigger', 'helios-snapshot-trigger',
                  'hermes-snapshot-trigger', 'eris-snapshot-trigger');

-- 2) New schedule (times are UTC, weekdays). Chosen to be inside market
--    hours in both EST and EDT:
--    analyst  15:00 UTC = 10:00 EST / 11:00 EDT
--             19:45 UTC = 14:45 EST / 15:45 EDT
--    monkey   15:00 UTC, the same time as the analyst's morning run
--    snapshot every 15 min 13:00-21:59 UTC (the script skips outside ~9:00-16:30 ET)
select cron.schedule('analyst-am', '0 15 * * 1-5',  $$select public.trigger_github_workflow('analyst.yml')$$);
select cron.schedule('analyst-pm', '45 19 * * 1-5', $$select public.trigger_github_workflow('analyst.yml')$$);
select cron.schedule('monkey',     '0 15 * * 1-5',  $$select public.trigger_github_workflow('monkey.yml')$$);
select cron.schedule('snapshot',   '*/15 13-21 * * 1-5', $$select public.trigger_github_workflow('snapshot.yml')$$);
