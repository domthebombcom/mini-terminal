import asyncio
import base64
import csv
import io
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.requests import Request

app = FastAPI(title="Telegram Channel Catalog")
templates = Jinja2Templates(directory="templates")


@dataclass
class TelegramConfig:
    api_id: Optional[int]
    api_hash: Optional[str]
    string_session: Optional[str]


def load_telegram_config() -> TelegramConfig:
    api_id_raw = os.getenv("TELEGRAM_API_ID", "").strip()
    api_hash = os.getenv("TELEGRAM_API_HASH", "").strip() or None
    string_session = os.getenv("TELEGRAM_STRING_SESSION", "").strip() or None

    api_id: Optional[int] = None
    if api_id_raw:
        try:
            api_id = int(api_id_raw)
        except ValueError as exc:
            raise HTTPException(status_code=500, detail="TELEGRAM_API_ID must be an integer") from exc

    return TelegramConfig(api_id=api_id, api_hash=api_hash, string_session=string_session)


class ScrapeRequest(BaseModel):
    channels: List[str] = Field(default_factory=list)
    limit_per_channel: int = Field(default=100, ge=1, le=1000)
    include_image_data: bool = True


class PostRecord(BaseModel):
    channel: str
    post_id: int
    timestamp_utc: str
    text: str
    text_length: int
    word_count: int
    has_image: bool
    media_type: str
    image_mime_type: Optional[str] = None
    image_size_bytes: Optional[int] = None
    image_base64: Optional[str] = None


class ScrapeResponse(BaseModel):
    records: List[PostRecord]
    summary: dict


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/telegram/config")
async def telegram_config_status():
    cfg = load_telegram_config()
    return {
        "api_id_set": cfg.api_id is not None,
        "api_hash_set": cfg.api_hash is not None,
        "string_session_set": cfg.string_session is not None,
    }


async def build_client(cfg: TelegramConfig):
    if not cfg.api_id or not cfg.api_hash:
        raise HTTPException(
            status_code=400,
            detail="Missing TELEGRAM_API_ID or TELEGRAM_API_HASH. Set both in your environment.",
        )

    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="telethon is not installed. Run `pip install -r requirements.txt`.") from exc

    session = StringSession(cfg.string_session) if cfg.string_session else "telegram-session"
    client = TelegramClient(session, cfg.api_id, cfg.api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        await client.disconnect()
        raise HTTPException(
            status_code=400,
            detail=(
                "Telegram session is not authorized. Generate TELEGRAM_STRING_SESSION using your own account "
                "(or authorize the local session file once) before scraping."
            ),
        )

    return client


async def extract_image_payload(message, include_image_data: bool):
    if not message.photo:
        return None

    if not include_image_data:
        return {"image_mime_type": "image/jpeg", "image_size_bytes": None, "image_base64": None}

    data = await message.download_media(file=bytes)
    if not data:
        return {"image_mime_type": "image/jpeg", "image_size_bytes": None, "image_base64": None}

    mime = "image/jpeg"
    encoded = base64.b64encode(data).decode("utf-8")
    return {
        "image_mime_type": mime,
        "image_size_bytes": len(data),
        "image_base64": f"data:{mime};base64,{encoded}",
    }


@app.post("/api/telegram/scrape", response_model=ScrapeResponse)
async def scrape_telegram_posts(payload: ScrapeRequest):
    channels = [c.strip() for c in payload.channels if c.strip()]
    if not channels:
        raise HTTPException(status_code=400, detail="Provide at least one channel username/link.")

    cfg = load_telegram_config()
    client = await build_client(cfg)

    records: List[PostRecord] = []
    try:
        for channel in channels:
            try:
                entity = await client.get_entity(channel)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Unable to resolve channel: {channel}") from exc

            async for message in client.iter_messages(entity, limit=payload.limit_per_channel):
                if not message:
                    continue

                text = (message.message or "").strip()
                media_type = "photo" if message.photo else ("video" if message.video else ("document" if message.document else "none"))
                image_data = await extract_image_payload(message, payload.include_image_data)

                ts = message.date
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                ts_iso = ts.astimezone(timezone.utc).isoformat()

                records.append(
                    PostRecord(
                        channel=channel,
                        post_id=message.id,
                        timestamp_utc=ts_iso,
                        text=text,
                        text_length=len(text),
                        word_count=len(text.split()) if text else 0,
                        has_image=bool(message.photo),
                        media_type=media_type,
                        image_mime_type=image_data["image_mime_type"] if image_data else None,
                        image_size_bytes=image_data["image_size_bytes"] if image_data else None,
                        image_base64=image_data["image_base64"] if image_data else None,
                    )
                )

    except Exception as exc:
        err_name = exc.__class__.__name__
        if err_name in {"RPCError", "FloodWaitError", "AuthKeyError"}:
            raise HTTPException(status_code=502, detail=f"Telegram API error: {exc}") from exc
        raise
    finally:
        await client.disconnect()

    records.sort(key=lambda x: x.timestamp_utc, reverse=True)

    summary = {
        "total_posts": len(records),
        "channels": sorted(list({r.channel for r in records})),
        "posts_with_images": sum(1 for r in records if r.has_image),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    return ScrapeResponse(records=records, summary=summary)


@app.post("/api/telegram/export.csv")
async def export_csv(payload: ScrapeRequest):
    scrape_result = await scrape_telegram_posts(payload)

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "channel",
            "post_id",
            "timestamp_utc",
            "text",
            "text_length",
            "word_count",
            "has_image",
            "media_type",
            "image_mime_type",
            "image_size_bytes",
        ],
    )
    writer.writeheader()
    for row in scrape_result.records:
        writer.writerow(
            {
                "channel": row.channel,
                "post_id": row.post_id,
                "timestamp_utc": row.timestamp_utc,
                "text": row.text,
                "text_length": row.text_length,
                "word_count": row.word_count,
                "has_image": row.has_image,
                "media_type": row.media_type,
                "image_mime_type": row.image_mime_type,
                "image_size_bytes": row.image_size_bytes,
            }
        )

    output.seek(0)
    filename = f"telegram-posts-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
