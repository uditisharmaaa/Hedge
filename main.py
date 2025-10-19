# main.py
from game_server import app             # 先加载 app 和共享状态
from trading_api import trading_router  # 再加载 trading 路由

app.include_router(trading_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
