import asyncio
import json
import os
import time
from typing import Dict, Set, List
import urllib.parse
import urllib.request

import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
FRED_API_KEY = os.getenv("FRED_API_KEY", "").strip()
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "").strip()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Latest tick cache: symbol -> tick dict
LATEST: Dict[str, dict] = {}

class Client:
    def __init__(self, ws: WebSocket, symbols: Set[str]):
        self.ws = ws
        self.symbols = symbols

CLIENTS: Set[Client] = set()

def binance_stream_url(symbols: List[str]) -> str:
    streams = "/".join([f"{s.lower()}@miniTicker" for s in symbols])
    return f"wss://stream.binance.com:9443/stream?streams={streams}"

async def binance_consumer(symbols: List[str]):
    url = binance_stream_url(symbols)
    backoff = 1

    while True:
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                backoff = 1
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)

                    payload = data.get("data", {})
                    symbol = payload.get("s")
                    if not symbol:
                        continue

                    tick = {
                        "symbol": symbol,
                        "last": float(payload.get("c", "nan")),
                        "open": float(payload.get("o", "nan")),
                        "high": float(payload.get("h", "nan")),
                        "low": float(payload.get("l", "nan")),
                        "volume": float(payload.get("v", "nan")),
                        "ts": int(time.time() * 1000),
                    }
                    LATEST[symbol] = tick

                    dead_clients = []
                    for client in list(CLIENTS):
                        if symbol in client.symbols:
                            try:
                                await client.ws.send_text(json.dumps(tick))
                            except Exception:
                                dead_clients.append(client)
                    for dc in dead_clients:
                        CLIENTS.discard(dc)

        except Exception:
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)

@app.on_event("startup")
async def startup():
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    asyncio.create_task(binance_consumer(symbols))

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        query = websocket.query_params.get("symbols", "BTCUSDT,ETHUSDT")
        symbols = {s.strip().upper() for s in query.split(",") if s.strip()}
        client = Client(websocket, symbols)
        CLIENTS.add(client)

        # Send snapshot immediately
        for s in symbols:
            if s in LATEST:
                await websocket.send_text(json.dumps(LATEST[s]))

        while True:
            # Keep connection alive; we don't require client messages yet
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass
    finally:
        to_remove = [c for c in CLIENTS if c.ws == websocket]
        for c in to_remove:
            CLIENTS.discard(c)

def _http_get_json(url: str, timeout: int = 10):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "mini-terminal/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

@app.get("/api/candles")
async def get_candles(symbol: str = "BTCUSDT", interval: str = "1m", limit: int = 500):
    """
    Free historical candles from Binance Klines API.
    interval examples: 1m, 5m, 15m, 1h, 4h, 1d
    """
    symbol = symbol.strip().upper()
    interval = interval.strip()
    limit = max(10, min(int(limit), 1000))

    params = urllib.parse.urlencode({"symbol": symbol, "interval": interval, "limit": limit})
    url = f"https://api.binance.com/api/v3/klines?{params}"
    raw = _http_get_json(url)

    candles = []
    for k in raw:
        open_time_ms = int(k[0])
        candles.append({
            "time": open_time_ms // 1000,  # seconds
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        })

    return {"symbol": symbol, "interval": interval, "candles": candles}
