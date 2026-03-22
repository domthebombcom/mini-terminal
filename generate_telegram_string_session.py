from telethon.sync import TelegramClient
from telethon.sessions import StringSession


def prompt_api_id() -> int:
    raw_value = input("Telegram API ID: ").strip()
    if not raw_value.isdigit():
        raise SystemExit("Telegram API ID must be a numeric value.")
    return int(raw_value)


def main() -> None:
    print("Generate a reusable TELEGRAM_STRING_SESSION using your own Telegram account.\n")
    api_id = prompt_api_id()
    api_hash = input("Telegram API Hash: ").strip()

    with TelegramClient(StringSession(), api_id, api_hash) as client:
        string_session = client.session.save()

    print("\nCopy this into your environment before starting the app:\n")
    print(f"TELEGRAM_STRING_SESSION={string_session}")


if __name__ == "__main__":
    main()
