import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from telethon import TelegramClient
from telethon.tl.types import User, Channel, Message
from config import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE

class DebugTools:
    def __init__(self):
        self.api_id = TELEGRAM_API_ID
        self.api_hash = TELEGRAM_API_HASH
        self.phone = TELEGRAM_PHONE
        self.client = None
        
    async def start_client(self):
        """Запуск клиента Telegram"""
        try:
            self.client = TelegramClient('debug_session', self.api_id, self.api_hash)
            await self.client.start(phone=self.phone)
            print("✅ Debug клиент запущен")
            return True
        except Exception as e:
            print(f"❌ Ошибка запуска debug клиента: {e}")
            return False
    
    async def stop_client(self):
        """Остановка клиента"""
        if self.client:
            await self.client.disconnect()
            print("✅ Debug клиент остановлен")
    
    async def get_account_info(self) -> Dict:
        """Получает информацию об аккаунте"""
        if not self.client:
            return {"error": "Клиент не запущен"}
        
        try:
            me = await self.client.get_me()
            return {
                "id": me.id,
                "username": me.username,
                "first_name": me.first_name,
                "last_name": me.last_name,
                "phone": me.phone,
                "is_bot": me.bot,
                "verified": me.verified,
                "premium": getattr(me, 'premium', False),
                "status": "online" if await self.client.is_user_authorized() else "offline"
            }
        except Exception as e:
            return {"error": f"Ошибка получения информации: {e}"}
    
    async def get_last_messages(self, limit: int = 5) -> List[Dict]:
        """Получает последние сообщения из всех диалогов"""
        if not self.client:
            return []
        
        try:
            messages = []
            async for dialog in self.client.iter_dialogs(limit=10):
                try:
                    # Получаем последнее сообщение из диалога
                    last_message = await self.client.get_messages(dialog, limit=1)
                    if last_message and last_message[0]:
                        msg = last_message[0]
                        msg_data = {
                            'id': msg.id,
                            'text': msg.text[:200] + "..." if msg.text and len(msg.text) > 200 else msg.text,
                            'date': msg.date.isoformat(),
                            'from_user': getattr(msg.sender, 'username', 'Unknown'),
                            'chat_title': dialog.title,
                            'chat_type': 'channel' if dialog.is_channel else 'user' if dialog.is_user else 'group'
                        }
                        messages.append(msg_data)
                except Exception as e:
                    print(f"Ошибка получения сообщения из {dialog.title}: {e}")
                    continue
            
            return messages[:limit]
            
        except Exception as e:
            return [{"error": f"Ошибка получения сообщений: {e}"}]
    
    async def get_dialogs_info(self) -> List[Dict]:
        """Получает информацию о диалогах"""
        if not self.client:
            return []
        
        try:
            dialogs = []
            async for dialog in self.client.iter_dialogs(limit=20):
                dialog_info = {
                    'title': dialog.title,
                    'username': getattr(dialog.entity, 'username', None),
                    'type': 'channel' if dialog.is_channel else 'user' if dialog.is_user else 'group',
                    'unread_count': dialog.unread_count,
                    'last_message_date': dialog.date.isoformat() if dialog.date else None
                }
                dialogs.append(dialog_info)
            
            return dialogs
            
        except Exception as e:
            return [{"error": f"Ошибка получения диалогов: {e}"}]
    
    async def send_message_to_user(self, username: str, message: str) -> Dict:
        """Отправляет сообщение пользователю"""
        if not self.client:
            return {"error": "Клиент не запущен"}
        
        try:
            # Получаем пользователя
            user = await self.client.get_entity(username)
            
            # Отправляем сообщение
            sent_message = await self.client.send_message(user, message)
            
            return {
                "success": True,
                "message_id": sent_message.id,
                "to_user": username,
                "text": message,
                "date": sent_message.date.isoformat()
            }
            
        except Exception as e:
            return {"error": f"Ошибка отправки сообщения: {e}"}
    
    async def test_connection(self) -> Dict:
        """Тестирует подключение к Telegram"""
        try:
            if not self.client:
                await self.start_client()
            
            if not self.client:
                return {"status": "error", "message": "Не удалось запустить клиент"}
            
            # Проверяем авторизацию
            is_authorized = await self.client.is_user_authorized()
            
            if not is_authorized:
                return {"status": "error", "message": "Пользователь не авторизован"}
            
            # Получаем информацию об аккаунте
            me = await self.client.get_me()
            
            return {
                "status": "success",
                "message": "Подключение успешно",
                "account": {
                    "id": me.id,
                    "username": me.username,
                    "first_name": me.first_name,
                    "phone": me.phone
                }
            }
            
        except Exception as e:
            return {"status": "error", "message": f"Ошибка подключения: {e}"} 