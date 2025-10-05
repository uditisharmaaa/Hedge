import os
from supabase import create_client
from dotenv import load_dotenv

# 1) Load variables from .env in the current folder
load_dotenv(dotenv_path=".env")

# 2) Read them safely (no KeyError if missing)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    print("❌ Missing SUPABASE_URL or SUPABASE_ANON_KEY in .env")
    print("   - Check the file is in the same folder as this script")
    print("   - Lines should be exactly:\n     SUPABASE_URL=...\n     SUPABASE_ANON_KEY=...")
    raise SystemExit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
res = supabase.table("tickers").select("*").execute()
print("✅ Connected! tickers count:", len(res.data))
