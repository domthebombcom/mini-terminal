# Mini Terminal (free data)

This is a Bloomberg-style mini terminal using **free** Binance data:
- Real-time crypto quotes via Binance WebSocket (miniTicker)
- Candlestick charts via Binance REST klines
- Command bar + hotkeys
- Live candle updates from ticks

## Run locally
1) Install Python 3.10+
2) In this folder:
   - `python -m venv .venv`
   - `source .venv/bin/activate` (Windows: `.venv\Scripts\activate`)
   - `pip install -r requirements.txt`
3) Start:
   - `uvicorn app:app --reload --port 8000`
4) Open:
   - http://localhost:8000

## Deploy to Render (private-ish link)
1) Put this repo on GitHub
2) In Render: New + → Blueprint → select repo → Apply
3) Use the provided URL on your phone.

Note: Render free plan may sleep when idle.
