-- Tables for the two-agent setup (analyst + monkey). The old
-- trading_agent_* / agent_* tables from the four-agent era are left as-is,
-- untouched, so nothing is lost; drop them whenever you like.

create table if not exists public.pt_runs (
  id            bigint generated always as identity primary key,
  agent_id      text not null check (agent_id in ('analyst', 'monkey')),
  run_at        timestamptz not null default now(),
  trigger       text,
  market_open   boolean,
  model         text,
  equity        numeric,
  cash          numeric,
  num_positions int,
  market_view   text,
  summary       jsonb not null default '{}'::jsonb   -- journal, seed, counts, errors
);
create index if not exists pt_runs_agent_time on public.pt_runs (agent_id, run_at desc);

create table if not exists public.pt_decisions (
  id          bigint generated always as identity primary key,
  run_id      bigint references public.pt_runs (id) on delete cascade,
  agent_id    text not null,
  created_at  timestamptz not null default now(),
  symbol      text not null,
  action      text not null,          -- buy | sell | short | cover
  size_pct    numeric,
  qty         numeric,
  fraction    numeric,
  est_price   numeric,
  confidence  numeric,
  thesis      text,
  exit_plan   text,
  status      text not null,          -- submitted | rejected | error | dry_run
  note        text,
  order_id    text
);
create index if not exists pt_decisions_agent_time on public.pt_decisions (agent_id, created_at desc);
create index if not exists pt_decisions_run on public.pt_decisions (run_id);

create table if not exists public.pt_snapshots (
  id           bigint generated always as identity primary key,
  agent_id     text not null,
  taken_at     timestamptz not null default now(),
  equity       numeric not null,
  cash         numeric,
  long_value   numeric,
  short_value  numeric,
  spy_price    numeric,
  positions    jsonb not null default '[]'::jsonb
);
create index if not exists pt_snapshots_agent_time on public.pt_snapshots (agent_id, taken_at desc);

-- The dashboard reads with the public anon key: read-only. Writes come from
-- GitHub Actions with the service-role key, which bypasses RLS.
alter table public.pt_runs      enable row level security;
alter table public.pt_decisions enable row level security;
alter table public.pt_snapshots enable row level security;
drop policy if exists "anon read" on public.pt_runs;
drop policy if exists "anon read" on public.pt_decisions;
drop policy if exists "anon read" on public.pt_snapshots;
create policy "anon read" on public.pt_runs      for select to anon, authenticated using (true);
create policy "anon read" on public.pt_decisions for select to anon, authenticated using (true);
create policy "anon read" on public.pt_snapshots for select to anon, authenticated using (true);
