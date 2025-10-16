from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
import random
import string


app = FastAPI(title="Hedge Game Server")

# Enums
class GameStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"

class PlayerLevel(str, Enum):
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"
    EXPERT = "EXPERT"

# Models
class ProfileCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    full_name: str

class ProfileResponse(BaseModel):
    id: str
    username: str
    full_name: str
    level: PlayerLevel = PlayerLevel.BEGINNER
    total_games: int = 0

class GameCreate(BaseModel):
    starting_cash: float = Field(default=100000.0, gt=0)

class GameResponse(BaseModel):
    id: int
    code: str
    starting_cash: float
    status: GameStatus
    participants_count: int = 0

class MatchRequest(BaseModel):
    player_id: str
    preferred_level: Optional[PlayerLevel] = None

class LeaderboardEntry(BaseModel):
    rank: int
    username: str
    total_points: int

# In-memory storage
profiles = {}
games = {}
matchmaking_queue = []
game_id = 1

def gen_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def check_compatibility(lvl1: PlayerLevel, lvl2: PlayerLevel) -> bool:
    levels = {PlayerLevel.BEGINNER: 0, PlayerLevel.INTERMEDIATE: 1, 
              PlayerLevel.ADVANCED: 2, PlayerLevel.EXPERT: 3}
    return abs(levels[lvl1] - levels[lvl2]) <= 1

# ============ PROFILES CRUD ============
@app.post("/profiles", status_code=201, response_model=ProfileResponse)
async def create_profile(p: ProfileCreate):
    if any(x['username'] == p.username for x in profiles.values()):
        raise HTTPException(409, f"Username '{p.username}' exists")
    pid = f"user_{len(profiles) + 1}"
    profiles[pid] = {"id": pid, "username": p.username, "full_name": p.full_name, 
                     "level": PlayerLevel.BEGINNER, "total_games": 0}
    return profiles[pid]

@app.get("/profiles", response_model=List[ProfileResponse])
async def list_profiles(level: Optional[PlayerLevel] = None):
    result = list(profiles.values())
    if level:
        result = [p for p in result if p['level'] == level]
    return result

@app.get("/profiles/{pid}", response_model=ProfileResponse)
async def get_profile(pid: str):
    if pid not in profiles:
        raise HTTPException(404, "Profile not found")
    return profiles[pid]

@app.put("/profiles/{pid}", response_model=ProfileResponse)
async def update_profile(pid: str, full_name: str):
    if pid not in profiles:
        raise HTTPException(404, "Profile not found")
    profiles[pid]['full_name'] = full_name
    return profiles[pid]

@app.delete("/profiles/{pid}", status_code=204)
async def delete_profile(pid: str):
    if pid not in profiles:
        raise HTTPException(404, "Profile not found")
    del profiles[pid]

# ============ GAMES CRUD ============
@app.post("/games", status_code=201, response_model=GameResponse)
async def create_game(g: GameCreate):
    global game_id
    gid = game_id
    games[gid] = {"id": gid, "code": gen_code(), "starting_cash": g.starting_cash,
                  "status": GameStatus.PENDING, "participants_count": 0}
    game_id += 1
    return games[gid]

@app.get("/games", response_model=List[GameResponse])
async def list_games(status: Optional[GameStatus] = None):
    result = list(games.values())
    if status:
        result = [g for g in result if g['status'] == status]
    return result

@app.get("/games/{gid}", response_model=GameResponse)
async def get_game(gid: int):
    if gid not in games:
        raise HTTPException(404, "Game not found")
    return games[gid]

@app.delete("/games/{gid}", status_code=204)
async def delete_game(gid: int):
    if gid not in games:
        raise HTTPException(404, "Game not found")
    if games[gid]['status'] != GameStatus.PENDING:
        raise HTTPException(400, "Can only delete pending games")
    del games[gid]

# ============ PLAYER ACTIONS ============
@app.post("/games/{gid}/join")
async def join_game(gid: int, player_id: str):
    if gid not in games:
        raise HTTPException(404, "Game not found")
    if player_id not in profiles:
        raise HTTPException(404, "Player not found")
    if games[gid]['status'] != GameStatus.PENDING:
        raise HTTPException(400, "Game not accepting players")
    
    games[gid]['participants_count'] += 1
    return {"message": "Joined", "game_code": games[gid]['code']}

@app.get("/players/{pid}/stats")
async def get_player_stats(pid: str):
    if pid not in profiles:
        raise HTTPException(404, "Player not found")
    return {**profiles[pid], "total_trades": 0, "avg_response_ms": 1500}

# ============ LEADERBOARD ============
@app.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(limit: int = Query(10, ge=1, le=100)):
    sorted_profiles = sorted(profiles.values(), 
                            key=lambda x: x['total_games'], reverse=True)
    return [LeaderboardEntry(rank=i+1, username=p['username'], 
                            total_points=p['total_games']*100)
            for i, p in enumerate(sorted_profiles[:limit])]

# ============ MATCHMAKING ============
@app.post("/matches", status_code=201)
async def create_match(req: MatchRequest):
    if req.player_id not in profiles:
        raise HTTPException(404, "Player not found")
    
    player = profiles[req.player_id]
    
    # Find compatible match
    for i, queued in enumerate(matchmaking_queue):
        if check_compatibility(player['level'], profiles[queued]['level']):
            matched = matchmaking_queue.pop(i)
            
            # Create and start game
            g = await create_game(GameCreate())
            await join_game(g.id, req.player_id)
            await join_game(g.id, matched)
            games[g.id]['status'] = GameStatus.IN_PROGRESS
            
            return {"status": "matched", "game_id": g.id, "game_code": g.code}
    
    # No match - add to queue
    matchmaking_queue.append(req.player_id)
    return {"status": "queued", "position": len(matchmaking_queue)}

@app.delete("/matches/{pid}")
async def leave_matchmaking(pid: str):
    if pid not in matchmaking_queue:
        raise HTTPException(404, "Not in queue")
    matchmaking_queue.remove(pid)
    return {"message": "Removed from queue"}

@app.get("/health")
async def health():
    return {"profiles": len(profiles), "games": len(games), "queue": len(matchmaking_queue)}

# Load test data on startup
@app.on_event("startup")
async def load_test_data():
    global game_id
    
    # Create test profiles
    test_users = [
        {"username": "speedtrader", "full_name": "Alice Speed", "level": PlayerLevel.EXPERT, "total_games": 50},
        {"username": "hedgefund", "full_name": "Bob Hedge", "level": PlayerLevel.ADVANCED, "total_games": 30},
        {"username": "rookie123", "full_name": "Charlie New", "level": PlayerLevel.BEGINNER, "total_games": 5},
        {"username": "protrader", "full_name": "Diana Pro", "level": PlayerLevel.INTERMEDIATE, "total_games": 15},
    ]
    
    for i, user in enumerate(test_users, 1):
        uid = f"user_{i}"
        profiles[uid] = {
            "id": uid,
            "username": user["username"],
            "full_name": user["full_name"],
            "level": user["level"],
            "total_games": user["total_games"]
        }
    
    # Create test games
    test_games = [
        {"starting_cash": 100000.0, "status": GameStatus.IN_PROGRESS, "participants_count": 2},
        {"starting_cash": 50000.0, "status": GameStatus.PENDING, "participants_count": 1},
        {"starting_cash": 200000.0, "status": GameStatus.COMPLETED, "participants_count": 4},
    ]
    
    for g in test_games:
        games[game_id] = {
            "id": game_id,
            "code": gen_code(),
            "starting_cash": g["starting_cash"],
            "status": g["status"],
            "participants_count": g["participants_count"]
        }
        game_id += 1
    
    print("\n" + "="*60)
    print("HEDGE GAME SERVER STARTED")
    print("="*60)
    print(f"Loaded {len(profiles)} test profiles")
    print(f"Loaded {len(games)} test games")
    print(f"API Docs: http://localhost:8000/docs")
    print(f"Health Check: http://localhost:8000/health")
    print("="*60 + "\n")


from trading_api import trading_router
app.include_router(trading_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)