# try to use main.py to combine both game_server and trading_api
from game_server import app             # get app
from trading_api import trading_router  # get trading router
# connect both
app.include_router(trading_router)

import os
from fastapi import FastAPI, HTTPException
from supabase import create_client
from dotenv import load_dotenv

# 1) load environment variables & connect to Supabase
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    print("Miss Supabase credentials. Check your .env file.")
    supabase = None
else:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        print("Connected to Supabase successfully.")
    except Exception as e:
        print("Failed to connect to Supabase:", e)
        supabase = None

# 2) Database health check endpoint
@app.get("/db/health")
async def check_db():
    if supabase is None:
        raise HTTPException(status_code=500, detail="Supabase client not initialized")
    try:
        result = supabase.table("profiles").select("*").limit(1).execute()
        return {"db": "ok", "rows_found": len(result.data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

# 3) Run the app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
