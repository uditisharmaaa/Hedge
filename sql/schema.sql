-- =============================================================
-- Hedge (Black Swan Challenge) - Database Schema
-- =============================================================

-- ENUM TYPES
create type public.event_type as enum ('MACRO', 'MICRO');
create type public.event_severity as enum ('NORMAL', 'CRITICAL');
create type public.trade_side as enum ('BUY', 'SELL');

-- =============================================================
-- CORE TABLES
-- =============================================================

-- Tickers (stock universe)
create table if not exists public.tickers (
  id bigint generated always as identity primary key,
  symbol text unique not null,
  name text not null,
  sector text
);

-- Games (each multiplayer session)
create table if not exists public.games (
  id bigint generated always as identity primary key,
  code text unique not null,
  name text not null,
  created_at timestamptz default now()
);

-- Game participants (players joining a game)
create table if not exists public.game_participants (
  id bigint generated always as identity primary key,
  game_id bigint references public.games(id) on delete cascade,
  user_id uuid references auth.users(id) on delete cascade,
  created_at timestamptz default now(),
  unique (game_id, user_id)
);

-- Rounds (each event window in a game)
create table if not exists public.rounds (
  id bigint generated always as identity primary key,
  game_id bigint references public.games(id) on delete cascade,
  round_no integer not null,
  starts_at timestamptz default now(),
  ends_at timestamptz,
  unique (game_id, round_no)
);

-- =============================================================
-- EVENTS (Black Swan or micro news)
-- =============================================================
create table if not exists public.events (
  id bigint generated always as identity primary key,
  round_id bigint not null references public.rounds(id) on delete cascade,
  etype public.event_type not null,
  severity public.event_severity not null default 'NORMAL',
  headline text,
  description text,
  target_ticker_id bigint references public.tickers(id) on delete set null,
  impulse_pct numeric(6,2),
  created_at timestamptz default now()
);

-- =============================================================
-- PRICE SNAPSHOTS
-- =============================================================
create table if not exists public.price_snapshots (
  id bigint generated always as identity primary key,
  game_id bigint references public.games(id) on delete cascade,
  round_id bigint references public.rounds(id) on delete cascade,
  ticker_id bigint references public.tickers(id) on delete cascade,
  price numeric(10,2) not null,
  taken_at timestamptz default now()
);

-- =============================================================
-- TRADES (User decisions)
-- =============================================================
create table if not exists public.trades (
  id bigint generated always as identity primary key,
  participant_id bigint references public.game_participants(id) on delete cascade,
  ticker_id bigint references public.tickers(id) on delete cascade,
  side public.trade_side not null,
  quantity numeric(10,2) not null,
  price numeric(10,2) not null,
  executed_at timestamptz default now(),
  round_no integer,
  response_ms integer
);

-- =============================================================
-- SCORES (End of round summary)
-- =============================================================
create table if not exists public.round_scores (
  id bigint generated always as identity primary key,
  participant_id bigint references public.game_participants(id) on delete cascade,
  round_id bigint references public.rounds(id) on delete cascade,
  pnl numeric(12,2),
  accuracy_pct numeric(5,2),
  reaction_time_avg integer,
  created_at timestamptz default now()
);

-- =============================================================
-- RLS POLICIES
-- =============================================================

-- Enable RLS where user data is stored
alter table public.trades enable row level security;
alter table public.round_scores enable row level security;
alter table public.game_participants enable row level security;

-- Trades: users can see only their own trades
create policy "Allow users to view own trades"
  on public.trades for select
  using (
    participant_id in (
      select id from public.game_participants where user_id = auth.uid()
    )
  );

create policy "Allow users to insert own trades"
  on public.trades for insert
  with check (
    participant_id in (
      select id from public.game_participants where user_id = auth.uid()
    )
  );

-- Game participants: users can view only their own record
create policy "Users view own participation"
  on public.game_participants for select
  using (user_id = auth.uid());

create policy "Users insert themselves"
  on public.game_participants for insert
  with check (user_id = auth.uid());

-- Round scores: users view only their own
create policy "Users view own scores"
  on public.round_scores for select
  using (
    participant_id in (
      select id from public.game_participants where user_id = auth.uid()
    )
  );

-- =============================================================
-- END OF SCHEMA
-- =============================================================
