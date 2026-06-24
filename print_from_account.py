import asyncio
from datetime import datetime
from telethon import TelegramClient, events
from config import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE


async def main():
    client = TelegramClient('news_session', TELEGRAM_API_ID, TELEGRAM_API_HASH)
    await client.start(phone=TELEGRAM_PHONE)

    me = await client.get_me()
    me_name = " ".join(filter(None, [me.first_name, me.last_name])) or (f"@{me.username}" if me.username else str(me.id))
    print(f"✅ Вошли как: {me_name}")
    print("👂 Слушаю новые сообщения... (Ctrl+C для выхода)")

    @client.on(events.NewMessage())
    async def handler(event):
        try:
            if not event.message or not event.message.message:
                return
            chat = await event.get_chat()
            # Имя источника
            source = getattr(chat, 'title', None) or getattr(chat, 'username', None)
            if not source and hasattr(chat, 'first_name'):
                source = " ".join(filter(None, [getattr(chat, 'first_name', None), getattr(chat, 'last_name', None)])).strip()
            source = source or "личка/чат"

            # Время
            ts = event.message.date
            time_str = ts.strftime('%H:%M') if isinstance(ts, datetime) else "--:--"

            text = event.message.message.strip()
            if not text:
                return

            print(f"[{time_str}] [{source}] {text}")
        except Exception as e:
            print(f"❌ Ошибка обработчика: {e}")

    try:
        await client.run_until_disconnected()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())


