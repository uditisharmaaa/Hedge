# [Hedge Game —— game_server & trading] API

## What it does
This FastAPI connects to our Supabase database, so that it can support the Hedge market simulation game. It acts as a brain to becide whether to allow, reject, or adjust player's action based on the game rule (e.g.handling player registration, game creation, trade actions, leaderboard updates). By contrast, Supabase’s auto-generated API itself alone cannot enforce our multi-step business logic, since it lacks the ability to do the atomic operations, complex validations, or cross-table rules.

## Setup
1. `pip install -r requirements.txt`
2. Add `.env` with Supabase credentials
3. `uvicorn main:app --reload`
4. Test at http://localhost:8000/docs

## Endpoints (at a minimum)
- POST /profiles – Create a new player (unique name check).
- POST /games – Create a new game session.
- POST /games/{gid}/join – Player joins only if the game is in PENDING status.
- POST /matches – Matchmaking system pairs players with similar levels.
- POST /trading/trade – Place a trade with balance and position checks.
- GET /trading/portfolio – Return each player’s current holdings and PnL.
- GET /leaderboard – Display player rankings by total equity.

## Key Business Rule
Before a player joining or trading, the system will checks game status and data validity. After that, all trades are verified for sufficient balance, existing holdings, and current market prices, which can help to prevent short selling or overspending. Once validated these rules, each trade cycle willupdates the player’s cash and portfolio instantly to keep all records consistent.

## Limitation of Auto generate API

