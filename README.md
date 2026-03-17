# Telegram Channel Post Catalog

Web app to scrape Telegram channel posts that your own account can access, then analyze and catalog those posts in a sortable/filterable table with CSV export.

## Features
- QR code login flow in the app (scan with Telegram mobile app).
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

## Run
- `uvicorn app:app --reload --port 8000`
- Open `http://localhost:8000`

## Auth flow
1. Click **Generate QR** in the UI.
2. In Telegram mobile app: **Settings → Devices → Link Desktop Device**.
3. Scan QR and wait for "QR login successful".
4. (Optional) Copy the generated string session and save it as `TELEGRAM_STRING_SESSION` for persistent deployments.

## Notes
- Scraping is limited to channels that your account can access.
- Runtime QR sessions are in-memory; restarting the server requires re-login unless `TELEGRAM_STRING_SESSION` is set.
