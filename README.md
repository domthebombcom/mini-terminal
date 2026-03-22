# Telegram Channel Post Catalog

Web app to scrape Telegram channel posts that your own account can access, then analyze and catalog those posts in a sortable/filterable table with CSV export.

## Features
- Scrape posts from multiple Telegram channels/usernames/links.
- Capture UTC timestamp, post text, word counts, media type, and image previews (base64).
- Sort/filter the table by timestamp, channel, post ID, media type, and text fields.
- Export the catalog data to CSV.
- Use a reusable Telethon string session instead of saving a Telegram session file to disk.

## Setup
1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Set Telegram credentials in environment variables:
   - `TELEGRAM_API_ID` (integer)
   - `TELEGRAM_API_HASH`
   - `TELEGRAM_STRING_SESSION` (required)


### Telegram account setup (one-time)
Use your own Telegram account to generate a reusable `TELEGRAM_STRING_SESSION`:

```bash
python generate_telegram_string_session.py
```

The helper uses Telethon, walks you through Telegram login, and prints a reusable session string to your terminal. Store that value in your environment before starting the app:

```bash
export TELEGRAM_API_ID=1234567
export TELEGRAM_API_HASH=your_api_hash
export TELEGRAM_STRING_SESSION='paste_the_generated_value_here'
```

If you prefer to see the underlying Telethon pattern, the helper script is equivalent to:

```python
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

with TelegramClient(StringSession(), api_id, api_hash) as client:
    string_session = client.session.save()
```

## Run
- `uvicorn app:app --reload --port 8000`
- Open `http://localhost:8000`

## Notes
- This app uses your own Telegram account string session; separate account authorization/setup is required.
- Scraping is limited to channels that your account can access.
- The app does not fall back to a local Telegram session file, so `TELEGRAM_STRING_SESSION` must be present for scraping.
