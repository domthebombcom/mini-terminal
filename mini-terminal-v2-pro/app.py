
import asyncio, json, os, re, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import date
from typing import Dict, Set, List
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

app = FastAPI(title="Mini Terminal V2")
templates = Jinja2Templates(directory="templates")
APP_USER_AGENT = os.getenv("APP_USER_AGENT", "mini-terminal-v2/1.0 (contact: you@example.com)")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
LATEST: Dict[str, dict] = {}
CLIENTS: Set["Client"] = set()

CATALOG = [
    {"key":"BTCUSDT","label":"Bitcoin / USDT","type":"Crypto"},
    {"key":"ETHUSDT","label":"Ethereum / USDT","type":"Crypto"},
    {"key":"SOLUSDT","label":"Solana / USDT","type":"Crypto"},
    {"key":"AAPL","label":"Apple","type":"Equity"},
    {"key":"MSFT","label":"Microsoft","type":"Equity"},
    {"key":"NVDA","label":"NVIDIA","type":"Equity"},
    {"key":"SPY","label":"S&P 500 ETF","type":"ETF"},
    {"key":"QQQ","label":"Nasdaq 100 ETF","type":"ETF"},
    {"key":"VTSAX","label":"Vanguard Total Stock Market Index Fund","type":"Mutual Fund"},
    {"key":"UST 10Y","label":"10Y Treasury yield","type":"Rates"},
    {"key":"UST 10-2","label":"10Y-2Y Treasury spread","type":"Rates"},
    {"key":"CPI 20","label":"CPI (20y)","type":"Macro"},
    {"key":"UNRATE 20","label":"Unemployment rate (20y)","type":"Macro"},
    {"key":"GDP 30","label":"GDP (30y)","type":"Macro"},
]

class Client:
    def __init__(self, ws: WebSocket, symbols: Set[str]):
        self.ws = ws
        self.symbols = symbols

def _http_get_text(url: str, timeout: int = 20, headers: dict | None = None) -> str:
    h = {"User-Agent": APP_USER_AGENT}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")

def _http_get_json(url: str, timeout: int = 20, headers: dict | None = None):
    return json.loads(_http_get_text(url, timeout=timeout, headers=headers))

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
                    data = json.loads(await ws.recv())
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
                    dead = []
                    for client in list(CLIENTS):
                        if symbol in client.symbols:
                            try:
                                await client.ws.send_text(json.dumps(tick))
                            except Exception:
                                dead.append(client)
                    for dc in dead:
                        CLIENTS.discard(dc)
        except Exception:
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)

@app.on_event("startup")
async def startup():
    asyncio.create_task(binance_consumer(["BTCUSDT","ETHUSDT","SOLUSDT"]))

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/catalog")
async def api_catalog():
    return {"items": CATALOG}

@app.get("/api/candles")
async def get_crypto_candles(symbol: str = "BTCUSDT", interval: str = "1m", limit: int = 500):
    params = urllib.parse.urlencode({"symbol": symbol.strip().upper(), "interval": interval.strip(), "limit": max(10, min(int(limit), 1000))})
    raw = _http_get_json(f"https://api.binance.com/api/v3/klines?{params}")
    candles = [{"time": int(k[0]) // 1000, "open": float(k[1]), "high": float(k[2]), "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])} for k in raw]
    return {"symbol": symbol.upper(), "interval": interval, "candles": candles}

@app.get("/api/stooq/candles")
async def stooq_candles(symbol: str):
    s = symbol.strip().lower()
    if not re.search(r"\.[a-z]{2,4}$", s):
        s = f"{s}.us"
    raw = _http_get_text(f"https://stooq.com/q/d/l/?s={urllib.parse.quote(s)}&i=d")
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if len(lines) < 2:
        return {"symbol": s.upper(), "interval": "1d", "candles": []}
    header = lines[0].split(",")
    idx = {name.lower(): i for i, name in enumerate(header)}
    candles = []
    for ln in lines[1:]:
        parts = ln.split(",")
        if parts[idx.get("close", 4)] in ("", "N/A"):
            continue
        y, m, d = map(int, parts[idx["date"]].split("-"))
        t = int(time.mktime((y, m, d, 0, 0, 0, 0, 0, -1)))
        candles.append({"time": t, "open": float(parts[idx["open"]]), "high": float(parts[idx["high"]]), "low": float(parts[idx["low"]]), "close": float(parts[idx["close"]])})
    return {"symbol": s.upper(), "interval": "1d", "candles": candles, "source": "Stooq"}

@app.get("/api/av/daily")
async def alphavantage_daily(symbol: str, outputsize: str = "compact"):
    if not ALPHA_VANTAGE_API_KEY:
        return {"error": "Missing ALPHA_VANTAGE_API_KEY"}
    url = "https://www.alphavantage.co/query?" + urllib.parse.urlencode({"function":"TIME_SERIES_DAILY","symbol":symbol.strip().upper(),"outputsize":outputsize,"apikey":ALPHA_VANTAGE_API_KEY})
    data = _http_get_json(url, timeout=25)
    ts = data.get("Time Series (Daily)")
    if not isinstance(ts, dict):
        return {"error": "Alpha Vantage response did not include daily series", "raw": data}
    candles = []
    for d, v in ts.items():
        y, m, dd = map(int, d.split("-"))
        t = int(time.mktime((y, m, dd, 0, 0, 0, 0, 0, -1)))
        candles.append({"time": t, "open": float(v["1. open"]), "high": float(v["2. high"]), "low": float(v["3. low"]), "close": float(v["4. close"]), "volume": float(v.get("5. volume", 0) or 0)})
    candles.sort(key=lambda x: x["time"])
    return {"symbol": symbol.upper(), "interval": "1d", "candles": candles, "source": "Alpha Vantage"}

@app.get("/api/fred/series")
async def fred_series(ids: str, cosd: str | None = None):
    series_ids = [s.strip().upper() for s in ids.split(",") if s.strip()]
    params = {"id": ",".join(series_ids)}
    if cosd:
        params["cosd"] = cosd
    csv_text = _http_get_text("https://fred.stlouisfed.org/graph/fredgraph.csv?" + urllib.parse.urlencode(params))
    lines = [ln.strip() for ln in csv_text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return {"ids": series_ids, "series": {}}
    header = [h.strip() for h in lines[0].split(",")]
    col_idx = {name: i for i, name in enumerate(header)}
    out = {sid: [] for sid in series_ids}
    for ln in lines[1:]:
        parts = ln.split(",")
        if "DATE" not in col_idx:
            continue
        try:
            y, m, d = map(int, parts[col_idx["DATE"]].split("-"))
            t = int(time.mktime((y, m, d, 0, 0, 0, 0, 0, -1)))
        except Exception:
            continue
        for sid in series_ids:
            if sid not in col_idx:
                continue
            v = parts[col_idx[sid]]
            if v in ("", ".", "nan", "NaN", "null"):
                continue
            try:
                out[sid].append({"time": t, "value": float(v)})
            except Exception:
                pass
    return {"ids": series_ids, "series": out}

def _treasury_xml_url(data_key: str, year: int):
    return "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?" + urllib.parse.urlencode({"data": data_key, "field_tdr_date_value": str(year)})

def _parse_treasury_xml(xml_text: str):
    root = ET.fromstring(xml_text)
    ns = {"a":"http://www.w3.org/2005/Atom","m":"http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"}
    out = []
    for entry in root.findall("a:entry", ns):
        props = entry.find(".//m:properties", ns)
        if props is None:
            continue
        rec = {}
        for child in list(props):
            rec[child.tag.split("}",1)[-1]] = child.text
        out.append(rec)
    return out

@app.get("/api/ust/series")
async def ust_series(tenor: str = "BC_10YEAR"):
    year = date.today().year
    rows = _parse_treasury_xml(_http_get_text(_treasury_xml_url("daily_treasury_yield_curve", year), timeout=25))
    series = []
    for r in rows:
        d = (r.get("NEW_DATE") or r.get("DATE") or "").split("T",1)[0]
        if not d:
            continue
        try:
            y, m, day = map(int, d.split("-"))
            t = int(time.mktime((y, m, day, 0, 0, 0, 0, 0, -1)))
            fv = float(r.get(tenor) or "nan")
        except Exception:
            continue
        if fv == fv:
            series.append({"time": t, "value": fv})
    return {"tenor": tenor, "series": series}

@app.get("/api/ust/spread")
async def ust_spread(long_tenor: str = "BC_10YEAR", short_tenor: str = "BC_2YEAR"):
    year = date.today().year
    rows = _parse_treasury_xml(_http_get_text(_treasury_xml_url("daily_treasury_yield_curve", year), timeout=25))
    series = []
    for r in rows:
        d = (r.get("NEW_DATE") or r.get("DATE") or "").split("T",1)[0]
        if not d:
            continue
        try:
            y, m, day = map(int, d.split("-"))
            t = int(time.mktime((y, m, day, 0, 0, 0, 0, 0, -1)))
            lv = float(r.get(long_tenor) or "nan")
            sv = float(r.get(short_tenor) or "nan")
        except Exception:
            continue
        if lv == lv and sv == sv:
            series.append({"time": t, "value": lv - sv})
    return {"series": series}

_TICKER_MAP = None
def _load_ticker_map():
    global _TICKER_MAP
    if _TICKER_MAP is not None:
        return _TICKER_MAP
    data = _http_get_json("https://www.sec.gov/files/company_tickers.json", timeout=25, headers={"User-Agent": APP_USER_AGENT})
    mp = {}
    for _, row in data.items():
        t = (row.get("ticker") or "").upper()
        cik = row.get("cik_str")
        if t and cik is not None:
            mp[t] = str(cik).zfill(10)
    _TICKER_MAP = mp
    return mp

@app.get("/api/sec/filings")
async def sec_filings(ticker: str, count: int = 20):
    t = ticker.strip().upper()
    cik = _load_ticker_map().get(t)
    if not cik:
        return {"error": f"Unknown ticker {t}."}
    data = _http_get_json(f"https://data.sec.gov/submissions/CIK{cik}.json", timeout=25, headers={"User-Agent": APP_USER_AGENT})
    recent = (data.get("filings") or {}).get("recent") or {}
    items = []
    forms, acc, filing_date, primary_doc = recent.get("form") or [], recent.get("accessionNumber") or [], recent.get("filingDate") or [], recent.get("primaryDocument") or []
    n = min(count, len(forms), len(acc), len(filing_date), len(primary_doc))
    for i in range(n):
        accession = acc[i].replace("-", "")
        items.append({"form": forms[i], "filingDate": filing_date[i], "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{primary_doc[i]}"})
    return {"ticker": t, "items": items}

@app.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        query = websocket.query_params.get("symbols", "BTCUSDT,ETHUSDT")
        symbols = {s.strip().upper() for s in query.split(",") if s.strip()}
        client = Client(websocket, symbols)
        CLIENTS.add(client)
        for s in symbols:
            if s in LATEST:
                await websocket.send_text(json.dumps(LATEST[s]))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        for c in [c for c in CLIENTS if c.ws == websocket]:
            CLIENTS.discard(c)
