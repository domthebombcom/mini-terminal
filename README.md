# Telegram Channel Post Catalog

Web app to scrape Telegram channel posts that your own account can access, then analyze and catalog those posts in a sortable/filterable table with CSV export.

## Features
- Scrape posts from multiple Telegram channels/usernames/links.
- Capture UTC timestamp, post text, word counts, media type, and image previews (base64).
- Sort/filter the table by timestamp, channel, post ID, media type, and text fields.
- Export the catalog data to CSV.

## Setup
1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Set Telegram credentials in environment variables:
   - `TELEGRAM_API_ID` (integer)
   - `TELEGRAM_API_HASH`
   - `TELEGRAM_STRING_SESSION` (recommended, from your own account setup)


### Telegram account setup (one-time)
Use your own Telegram account to generate a reusable `TELEGRAM_STRING_SESSION`:

```bash
python - <<'PY'
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = int(input("API ID: "))
api_hash = input("API Hash: ").strip()
with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("\nTELEGRAM_STRING_SESSION=", client.session.save())
PY
```

Store that value in your environment before starting the app.

## Run
- `uvicorn app:app --reload --port 8000`
- Open `http://localhost:8000`

## Notes
- This app uses your own Telegram account session; separate account authorization/setup is required.
- Scraping is limited to channels that your account can access.
