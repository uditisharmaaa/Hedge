from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Tuple
from enum import Enum
from decimal import Decimal
from datetime import datetime


try:
    from game_server import profiles, games, GameStatus  
except Exception as e:
    profiles, games = {}, {}
    class GameStatus(str, Enum):
        PENDING = "PENDING"
        IN_PROGRESS = "IN_PROGRESS"
        COMPLETED = "COMPLETED"


# Router
trading_router = APIRouter(prefix="/trading", tags=["trading"])


# Enums & Models
class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class TickerCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=16, description="e.g., AAPL")
    name: Optional[str] = Field(None, max_length=120)
    sector: Optional[str] = Field(None, max_length=120)

class TickerResponse(BaseModel):
    id: int
    symbol: str
    name: Optional[str] = None
    sector: Optional[str] = None

class PriceSnapshotCreate(BaseModel):
    game_id: int = Field(..., ge=1)
    ticker_symbol: str
    price: Decimal = Field(..., gt=Decimal("0"))
    round_id: Optional[int] = Field(None, ge=1)
    taken_at: Optional[datetime] = None  

class PriceResponse(BaseModel):
    ticker_id: int
    symbol: str
    price: Decimal
    taken_at: datetime

class PlaceTradeRequest(BaseModel):
    game_id: int = Field(..., ge=1)
    player_id: str = Field(..., description="profiles.*.id")
    ticker_symbol: str
    side: Side
    quantity: Decimal = Field(..., gt=Decimal("0"))
    round_id: Optional[int] = Field(None, ge=1)

class TradeResponse(BaseModel):
    id: int
    game_id: int
    participant_key: str
    round_id: Optional[int]
    ticker_id: int
    symbol: str
    side: Side
    quantity: Decimal
    price: Decimal
    executed_at: datetime

class TradeListItem(BaseModel):
    id: int
    round_id: Optional[int]
    symbol: str
    side: Side
    quantity: Decimal
    price: Decimal
    executed_at: datetime

class Position(BaseModel):
    ticker_id: int
    symbol: str
    quantity: Decimal
    avg_price: Decimal
    market_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal

class PortfolioResponse(BaseModel):
    cash_balance: Decimal
    positions: List[Position]
    equity: Decimal
    unrealized_pnl_total: Decimal


# In-memory storage for trading domain
tickers: Dict[int, Dict] = {}
sym_index: Dict[str, int] = {}
ticker_id_seq: int = 1

# price_snapshots: List of dict rows 
price_snapshots: List[Dict] = []
ps_id_seq: int = 1

# trades: List of dict rows
trades: List[Dict] = []
trade_id_seq: int = 1

# participants cash ledger 
participants_cash: Dict[str, Decimal] = {}

def _participant_key(game_id: int, player_id: str) -> str:
    return f"{game_id}:{player_id}"


# Helpers
def _ensure_user_and_game(player_id: str, game_id: int) -> None:
    if player_id not in profiles:
        raise HTTPException(status_code=404, detail="Player not found")
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")

def _ensure_trading_allowed(game_id: int) -> None:
    g = games[game_id]
    if g["status"] not in (GameStatus.PENDING, GameStatus.IN_PROGRESS):
        raise HTTPException(status_code=400, detail="Trading not allowed in this game state")

def _get_or_create_participant(game_id: int, player_id: str) -> str:
    key = _participant_key(game_id, player_id)
    if key not in participants_cash:
        start_cash = Decimal(str(games[game_id].get("starting_cash", 100000.0)))
        participants_cash[key] = start_cash
    return key

def _require_ticker(symbol: str) -> Tuple[int, Dict]:
    sid = sym_index.get(symbol.upper())
    if not sid:
        raise HTTPException(status_code=404, detail=f"Ticker '{symbol}' not found")
    return sid, tickers[sid]

def _latest_price(game_id: int, ticker_id: int, round_id: Optional[int]) -> Dict:
    best = None
    if round_id is not None:
        for row in reversed(price_snapshots):
            if row["game_id"] == game_id and row["ticker_id"] == ticker_id and row.get("round_id") == round_id:
                best = row
                break
    if best is None:
        for row in reversed(price_snapshots):
            if row["game_id"] == game_id and row["ticker_id"] == ticker_id:
                best = row
                break
    if best is None:
        raise HTTPException(status_code=400, detail="No price snapshot available for this ticker")
    return best

def _position_quantity(participant_key: str, ticker_id: int) -> Decimal:
    qty = Decimal("0")
    for t in trades:
        if t["participant_key"] == participant_key and t["ticker_id"] == ticker_id:
            if t["side"] == Side.BUY:
                qty += t["quantity"]
            else:
                qty -= t["quantity"]
    return qty


# Endpoints

# Tickers (seed helpers)
@trading_router.post("/tickers", status_code=201, response_model=TickerResponse)
async def create_ticker(t: TickerCreate):
    global ticker_id_seq
    sym = t.symbol.upper()
    if sym in sym_index:
        raise HTTPException(status_code=409, detail=f"Ticker '{sym}' exists")
    tid = ticker_id_seq
    tickers[tid] = {"id": tid, "symbol": sym, "name": t.name, "sector": t.sector}
    sym_index[sym] = tid
    ticker_id_seq += 1
    return tickers[tid]

# Price snapshots
@trading_router.post("/price_snapshots", status_code=201, response_model=PriceResponse)
async def add_price_snapshot(ps: PriceSnapshotCreate):
    global ps_id_seq
    if ps.game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    tid, tk = _require_ticker(ps.ticker_symbol)
    row = {
        "id": ps_id_seq,
        "game_id": ps.game_id,
        "round_id": ps.round_id,
        "ticker_id": tid,
        "price": Decimal(ps.price),
        "taken_at": ps.taken_at or datetime.utcnow(),
    }
    price_snapshots.append(row)
    ps_id_seq += 1
    return PriceResponse(ticker_id=tid, symbol=tk["symbol"], price=row["price"], taken_at=row["taken_at"])

@trading_router.get("/price", response_model=PriceResponse)
async def get_price(
    symbol: str = Query(..., min_length=1, max_length=16),
    game_id: int = Query(..., ge=1),
    round_id: Optional[int] = Query(None, ge=1),
):
    tid, tk = _require_ticker(symbol)
    snap = _latest_price(game_id=game_id, ticker_id=tid, round_id=round_id)
    return PriceResponse(ticker_id=tid, symbol=tk["symbol"], price=snap["price"], taken_at=snap["taken_at"])

# Trading (business logic)
@trading_router.post("/trade", status_code=201, response_model=TradeResponse)
async def place_trade(body: PlaceTradeRequest):
    global trade_id_seq

    _ensure_user_and_game(body.player_id, body.game_id)
    _ensure_trading_allowed(body.game_id)
    pkey = _get_or_create_participant(body.game_id, body.player_id)

    
    tid, tk = _require_ticker(body.ticker_symbol)
    snap = _latest_price(game_id=body.game_id, ticker_id=tid, round_id=body.round_id)
    price = Decimal(snap["price"])
    qty = Decimal(body.quantity)


    current_qty = _position_quantity(pkey, tid)
    if body.side == Side.SELL and current_qty - qty < 0:
        raise HTTPException(status_code=400, detail="Insufficient position (shorting disabled)")
    notional = price * qty
    cash = participants_cash[pkey]
    if body.side == Side.BUY and cash < notional:
        raise HTTPException(status_code=400, detail="Insufficient cash")

    executed_at = datetime.utcnow()
    trade_row = {
        "id": trade_id_seq,
        "game_id": body.game_id,
        "participant_key": pkey,
        "round_id": body.round_id,
        "ticker_id": tid,
        "side": body.side,
        "quantity": qty,
        "price": price,
        "executed_at": executed_at,
    }
    trades.append(trade_row)
    trade_id_seq += 1

    if body.side == Side.BUY:
        participants_cash[pkey] = cash - notional
    else:
        participants_cash[pkey] = cash + notional

    return TradeResponse(
        id=trade_row["id"],
        game_id=body.game_id,
        participant_key=pkey,
        round_id=body.round_id,
        ticker_id=tid,
        symbol=tk["symbol"],
        side=body.side,
        quantity=qty,
        price=price,
        executed_at=executed_at,
    )

# Trade listing 
@trading_router.get("/trades", response_model=List[TradeListItem])
async def list_trades(
    game_id: int = Query(..., ge=1),
    player_id: str = Query(...),
    round_id: Optional[int] = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    _ensure_user_and_game(player_id, game_id)
    pkey = _get_or_create_participant(game_id, player_id)

    rows = [
        t for t in trades
        if t["game_id"] == game_id
        and t["participant_key"] == pkey
        and (round_id is None or t["round_id"] == round_id)
    ]
    rows.sort(key=lambda r: r["executed_at"], reverse=True)
    window = rows[offset: offset + limit]


    sym_by_tid = {tid: row["symbol"] for tid, row in tickers.items()}

    return [
        TradeListItem(
            id=r["id"],
            round_id=r["round_id"],
            symbol=sym_by_tid.get(r["ticker_id"], "?"),
            side=r["side"],
            quantity=r["quantity"],
            price=r["price"],
            executed_at=r["executed_at"],
        )
        for r in window
    ]

# Portfolio 
@trading_router.get("/portfolio", response_model=PortfolioResponse)
async def get_portfolio(
    game_id: int = Query(..., ge=1),
    player_id: str = Query(...),
):
    _ensure_user_and_game(player_id, game_id)
    pkey = _get_or_create_participant(game_id, player_id)

    cash = participants_cash[pkey]

    lots: Dict[int, Dict[str, Decimal]] = {}  
    for t in trades:
        if t["game_id"] != game_id or t["participant_key"] != pkey:
            continue
        tid = t["ticker_id"]
        lots.setdefault(tid, {"qty": Decimal("0"), "buy_cost": Decimal("0")})
        if t["side"] == Side.BUY:
            lots[tid]["qty"] += t["quantity"]
            lots[tid]["buy_cost"] += (t["quantity"] * t["price"])
        else:
            lots[tid]["qty"] -= t["quantity"]
            

    positions: List[Position] = []
    unreal_total = Decimal("0")
    equity = cash

    for tid, agg in lots.items():
        qty = agg["qty"]
        if qty == 0:
            continue
        avg_price = (agg["buy_cost"] / qty) if qty != 0 else Decimal("0")
        snap = _latest_price(game_id=game_id, ticker_id=tid, round_id=None)
        mkt_price = Decimal(snap["price"])
        mkt_val = qty * mkt_price
        unreal = (mkt_price - avg_price) * qty
        unreal_total += unreal
        equity += mkt_val
        positions.append(Position(
            ticker_id=tid,
            symbol=tickers[tid]["symbol"],
            quantity=qty,
            avg_price=avg_price,
            market_price=mkt_price,
            market_value=mkt_val,
            unrealized_pnl=unreal
        ))

    
    positions.sort(key=lambda p: p.symbol)

    return PortfolioResponse(
        cash_balance=cash,
        positions=positions,
        equity=equity,
        unrealized_pnl_total=unreal_total
    )

# Health
@trading_router.get("/health")
async def trading_health():
    return {
        "tickers": len(tickers),
        "price_snapshots": len(price_snapshots),
        "trades": len(trades),
        "participants": len(participants_cash),
    }
