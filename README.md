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

## Run
- `uvicorn app:app --reload --port 8000`
- Open `http://localhost:8000`

## Notes
- This app uses your own Telegram account session; separate account authorization/setup is required.
- Scraping is limited to channels that your account can access.
