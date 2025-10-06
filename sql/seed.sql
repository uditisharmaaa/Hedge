-- =============================================================
-- Hedge - Sample Data Seed
-- =============================================================

-- 1️⃣ Insert sample tickers
insert into public.tickers (symbol, name, sector) values
('AAPL', 'Apple Inc.', 'Technology'),
('MSFT', 'Microsoft Corp.', 'Technology'),
('TSLA', 'Tesla Motors', 'Automotive'),
('AMZN', 'Amazon.com Inc.', 'E-Commerce'),
('GOOG', 'Alphabet Inc.', 'Technology'),
('META', 'Meta Platforms', 'Social Media'),
('NVDA', 'NVIDIA Corp.', 'Semiconductors'),
('JPM', 'JPMorgan Chase', 'Finance'),
('XOM', 'ExxonMobil Corp.', 'Energy'),
('NFLX', 'Netflix Inc.', 'Entertainment');

-- 2️⃣ Insert demo game
insert into public.games (code, name) values ('ABC123', 'Demo Game');

-- 3️⃣ Insert rounds
insert into public.rounds (game_id, round_no, starts_at, ends_at) values
(1, 1, now(), now() + interval '5 min'),
(1, 2, now() + interval '6 min', now() + interval '11 min');

-- 4️⃣ Insert events (Black Swan news)
insert into public.events (round_id, etype, severity, headline, description, target_ticker_id, impulse_pct)
values
(1, 'MACRO', 'CRITICAL', 'Fed unexpectedly raises interest rates', 'Global market volatility spikes', 1, -5.0),
(2, 'MICRO', 'NORMAL', 'Tesla announces major breakthrough in battery tech', 'Boosts confidence in EV sector', 3, 7.5);

-- 5️⃣ Insert sample price snapshots
insert into public.price_snapshots (game_id, round_id, ticker_id, price)
values
(1, 1, 1, 185.00),
(1, 1, 2, 400.00),
(1, 1, 3, 345.00),
(1, 2, 1, 182.50),
(1, 2, 2, 415.00),
(1, 2, 3, 350.00);
