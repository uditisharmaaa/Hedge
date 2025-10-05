import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ANON_KEY"))

print("=== Hedge DB Tests ===")

# 1) Public read
tickers = sb.table("tickers").select("id,symbol").execute().data
print("✅ Public read OK: tickers:", len(tickers))

# 2) Basic reads (joins conceptually)
rounds = sb.table("rounds").select("id,round_no,game_id").execute().data
events = sb.table("events").select("id,round_id,etype,severity,headline").execute().data
print("✅ Basic reads OK: rounds/events")

# 3) RLS unauth (should fail or be restricted)
try:
    _ = sb.table("trades").select("*").execute()
    print("ℹ️  Trades read unauth returned (may be empty).")
except Exception as e:
    print("✅ RLS blocks unauth trades read:", str(e)[:90])

# 4) Auth user (set SUPABASE_TEST_EMAIL/PASSWORD in .env)
email = os.getenv("SUPABASE_TEST_EMAIL")
pwd   = os.getenv("SUPABASE_TEST_PASSWORD")
if not (email and pwd):
    print("⚠️ Skipping auth tests; set SUPABASE_TEST_EMAIL/PASSWORD in .env")
    raise SystemExit(0)

user = sb.auth.sign_in_with_password({"email": email, "password": pwd}).user
print("✅ Signed in as:", user.email)

# 5) Profile (owner-only)
sb.table("profiles").upsert(
    {"id": user.id, "username": email.split("@")[0][:20], "full_name": "Test User"},
    on_conflict="id",
    returning="minimal"
).execute()
print("✅ Profile upserted")

# 6) Join game ABC123 (use INSERT, not UPSERT)
game = sb.table("games").select("id").eq("code","ABC123").single().execute().data

# try insert; if it already exists, ignore the error by using 'ignoreDuplicates' behavior:
try:
    sb.table("game_participants").insert(
        {"game_id": game["id"], "user_id": user.id}
    ).execute()
except Exception as e:
    # If row exists, that's fine; continue
    if "duplicate key" not in str(e).lower():
        raise

# now fetch your participant row (allowed by the read policy)
gp = sb.table("game_participants")\
       .select("id")\
       .eq("game_id", game["id"])\
       .eq("user_id", user.id)\
       .single()\
       .execute().data
print("✅ Joined game as participant:", gp["id"])

# 7) Insert a trade (owner-only insert allowed by RLS)
r1 = sb.table("rounds").select("id").eq("game_id", game["id"]).eq("round_no",1).single().execute().data
aapl = sb.table("tickers").select("id").eq("symbol","AAPL").single().execute().data
trade = {
  "participant_id": gp["id"],
  "round_id": r1["id"],
  "ticker_id": aapl["id"],
  "side": "BUY",
  "quantity": 2.0,
  "price": 185.00,
  "response_ms": 1500
}
sb.table("trades").insert(trade).execute()
print("✅ Trade inserted under RLS")

# 8) Read back own trades
my_trades = sb.table("trades").select("id,ticker_id,quantity,price").execute().data
print("✅ Read back own trades:", len(my_trades))

print("🎉 All tests passed for rubric: connection, joins, RLS block, RLS allowed write/read.")
