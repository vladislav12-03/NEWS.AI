import asyncio
from telethon import TelegramClient
from config import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE

async def test_channels():
    """Тестируем подключение к каналам"""
    print("🔍 Тестируем подключение к Telegram...")
    
    client = TelegramClient('news_session', TELEGRAM_API_ID, TELEGRAM_API_HASH)
    await client.start(phone=TELEGRAM_PHONE)
    
    print("✅ Подключение успешно!")
    
    # Получаем все диалоги
    dialogs = await client.get_dialogs()
    channels = [d for d in dialogs if d.is_channel]
    
    print(f"\n📺 Найдено {len(channels)} каналов:")
    for i, dialog in enumerate(channels, 1):
        username = getattr(dialog.entity, 'username', 'unknown')
        title = getattr(dialog.entity, 'title', 'Неизвестный канал')
        print(f"{i}. {title} (@{username})")
    
    # Проверяем конкретно твой тестовый канал
    print(f"\n🔍 Проверяем канал @test_bot_tip_novosti...")
    try:
        channel = await client.get_entity('@test_bot_tip_novosti')
        print(f"✅ Канал найден: {getattr(channel, 'title', 'Неизвестный')}")
        
        # Получаем последние сообщения
        messages = []
        async for message in client.iter_messages(channel, limit=5):
            if message.text:
                messages.append({
                    'id': message.id,
                    'text': message.text[:100] + "..." if len(message.text) > 100 else message.text,
                    'date': message.date
                })
        
        print(f"📰 Найдено {len(messages)} сообщений:")
        for i, msg in enumerate(messages, 1):
            print(f"{i}. [{msg['date'].strftime('%H:%M')}] {msg['text']}")
            
    except Exception as e:
        print(f"❌ Ошибка при получении канала: {e}")
    
    await client.disconnect()
    print("\n✅ Тест завершен!")

if __name__ == "__main__":
    asyncio.run(test_channels()) 