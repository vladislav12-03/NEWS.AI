import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from telethon import TelegramClient, events
from telethon.tl.types import Channel, Message
from config import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE
import re
from zoneinfo import ZoneInfo

# === Фильтр мусора в новостях ===
MUSOR_PATTERNS = [
    r"ПІДПИСАТИСЬ", r"ПОДПИСАТЬСЯ", r"Subscribe", r"Підписуйся", r"Follow",
    r"Надсилайте новини", r"Отправить новость", r"бот", r"➡️", r"⤵️", r"👇",
    r"https?://\S+", r"t\.me/\S+", r"@[a-zA-Z0-9_]{3,}", r"Реклама", r"Рекламa",
    r"Співпраця", r"Контакт для реклами", r"Деталі:", r"Подробнее:",
    r"Читайте також:", r"Читайте также:", r"---", r"\*\*\*", r"ㅤ"
]

MUSOR_REGEX = re.compile(r"|".join(MUSOR_PATTERNS), re.IGNORECASE)

def filter_news_text(text: str) -> str:
    """Удаляет мусорные подписи и рекламу из текста новости."""
    lines = text.splitlines()
    filtered = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Если строка содержит мусорный паттерн — обрезаем новость на этом месте
        if MUSOR_REGEX.search(line):
            break
        # Удаляем строки, которые только ссылка или только упоминание
        if re.fullmatch(r"https?://\S+", line) or re.fullmatch(r"t\.me/\S+", line) or re.fullmatch(r"@[a-zA-Z0-9_]{3,}", line):
            continue
        # Удаляем строки, которые только эмодзи/разделители
        if re.fullmatch(r"[\W_]+", line):
            continue
        filtered.append(line)
    return "\n".join(filtered)

class ChannelReader:
    def __init__(self):
        self.api_id = TELEGRAM_API_ID
        self.api_hash = TELEGRAM_API_HASH
        self.phone = TELEGRAM_PHONE
        self.client = None
        self.last_messages = {}  # Кэш последних сообщений
        self.channels = None  # Список каналов будет получен динамически
        
    async def start(self):
        """Запуск клиента Telegram"""
        try:
            print("🔍 DEBUG: Запускаем Telegram клиент...")
            self.client = TelegramClient('news_session', self.api_id, self.api_hash)
            await self.client.start(phone=self.phone)
            print("✅ Telegram клиент запущен")
            
            # Получаем список каналов, на которые подписан аккаунт
            print("🔍 DEBUG: Получаем диалоги...")
            dialogs = await self.client.get_dialogs()
            print(f"🔍 DEBUG: Получено {len(dialogs)} диалогов")
            
            self.channels = [d.entity for d in dialogs if d.is_channel]
            print(f"🔍 DEBUG: Найдено {len(self.channels)} каналов для мониторинга.")
            
            # Выводим список каналов
            for i, channel in enumerate(self.channels, 1):
                username = getattr(channel, 'username', 'unknown')
                title = getattr(channel, 'title', 'Неизвестный канал')
                print(f"  {i}. {title} (@{username})")
            
            return True
        except Exception as e:
            print(f"❌ Ошибка запуска Telegram клиента: {e}")
            return False
    
    async def stop(self):
        """Остановка клиента"""
        if self.client:
            await self.client.disconnect()
            print("✅ Telegram клиент остановлен")
    
    async def get_channel_messages(self, channel_entity, limit: int = 20) -> List[Dict]:
        """Получает последние сообщения из канала по entity"""
        if not self.client:
            return []
        
        try:
            messages = []
            kyiv_tz = ZoneInfo("Europe/Kyiv")
            async for message in self.client.iter_messages(channel_entity, limit=limit):
                if message.text:  # Только текстовые сообщения
                    clean_text = filter_news_text(message.text)
                    if not clean_text:
                        continue
                    # Сохраняем дату в Europe/Kyiv
                    msg_data = {
                        'id': message.id,
                        'text': clean_text,
                        'date': message.date.astimezone(kyiv_tz).isoformat(),
                        'channel': getattr(channel_entity, 'username', getattr(channel_entity, 'title', 'unknown')),
                        'views': getattr(message, 'views', 0),
                        'forwards': getattr(message, 'forwards', 0)
                    }
                    messages.append(msg_data)
            
            return messages
            
        except Exception as e:
            print(f"❌ Ошибка чтения канала {getattr(channel_entity, 'username', getattr(channel_entity, 'title', 'unknown'))}: {e}")
            return []
    
    async def get_all_channels_messages(self, hours_back: int = 24) -> List[Dict]:
        """Получает сообщения из всех каналов за последние N часов"""
        print(f"🔍 DEBUG: get_all_channels_messages вызвана с hours_back={hours_back}")
        all_messages = []
        if not self.channels:
            print("🔍 DEBUG: Нет доступных каналов для мониторинга.")
            return []
        
        print(f"🔍 DEBUG: Обрабатываем {len(self.channels)} каналов")
        kyiv_tz = ZoneInfo("Europe/Kyiv")
        now_kyiv = datetime.now(kyiv_tz)
        for channel in self.channels:
            print(f"🔍 DEBUG: Обрабатываем канал {getattr(channel, 'username', getattr(channel, 'title', 'unknown'))}")
            messages = await self.get_channel_messages(channel)
            print(f"🔍 DEBUG: Получено {len(messages)} сообщений из канала")
            
            # Фильтруем по времени (Europe/Kyiv)
            cutoff_time = now_kyiv - timedelta(hours=hours_back)
            recent_messages = [
                msg for msg in messages 
                if datetime.fromisoformat(msg['date']).astimezone(kyiv_tz) > cutoff_time
            ]
            print(f"🔍 DEBUG: После фильтрации по времени осталось {len(recent_messages)} сообщений")
            
            all_messages.extend(recent_messages)
            print(f"📰 Канал {getattr(channel, 'username', getattr(channel, 'title', 'unknown'))}: {len(recent_messages)} новых сообщений")
        
        # Сортируем по дате
        all_messages.sort(key=lambda x: x['date'], reverse=True)
        print(f"🔍 DEBUG: Итого собрано {len(all_messages)} сообщений")
        return all_messages
    
    async def monitor_channels(self, callback_func):
        """Мониторинг каналов в реальном времени"""
        if not self.client or not self.channels:
            return
        
        @self.client.on(events.NewMessage(chats=[c.id for c in self.channels]))
        async def handle_new_message(event):
            try:
                message = event.message
                channel = await event.get_chat()
                
                if message.text:
                    clean_text = filter_news_text(message.text)
                    if not clean_text:
                        return
                    msg_data = {
                        'id': message.id,
                        'text': clean_text,
                        'date': message.date.replace(tzinfo=None).isoformat(),
                        'channel': getattr(channel, 'username', getattr(channel, 'title', 'unknown')),
                        'views': getattr(message, 'views', 0),
                        'forwards': getattr(message, 'forwards', 0)
                    }
                    
                    # Вызываем callback с новым сообщением
                    await callback_func(msg_data)
                    
            except Exception as e:
                print(f"❌ Ошибка обработки нового сообщения: {e}")
        
        print("👁️ Мониторинг каналов запущен")
        await self.client.run_until_disconnected()
    
    async def get_channel_info(self, channel_entity) -> Optional[Dict]:
        """Получает информацию о канале по entity"""
        if not self.client:
            return None
        
        try:
            return {
                'username': getattr(channel_entity, 'username', 'unknown'),
                'title': getattr(channel_entity, 'title', 'Неизвестный канал'),
                'participants_count': getattr(channel_entity, 'participants_count', 0),
                'description': getattr(channel_entity, 'about', '')
            }
        except Exception as e:
            print(f"❌ Ошибка получения информации о канале: {e}")
            return None 