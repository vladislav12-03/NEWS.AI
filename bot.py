import logging
import asyncio
import json
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from config import BOT_TOKEN, ADMIN_ID, DONATE_URL
from ai_processor import AIProcessor
from channel_reader import ChannelReader
import re

# Настройка логирования с красивыми сообщениями
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ANSI цвета для консоли
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def debug_print(message, color=Colors.OKCYAN, emoji="🔍"):
    """Красивая печать debug сообщений"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"{color}{emoji} [{timestamp}] DEBUG: {message}{Colors.ENDC}")

def success_print(message, emoji="✅"):
    """Красивая печать успешных операций"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"{Colors.OKGREEN}{emoji} [{timestamp}] SUCCESS: {message}{Colors.ENDC}")

def warning_print(message, emoji="⚠️"):
    """Красивая печать предупреждений"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"{Colors.WARNING}{emoji} [{timestamp}] WARNING: {message}{Colors.ENDC}")

def error_print(message, emoji="❌"):
    """Красивая печать ошибок"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"{Colors.FAIL}{emoji} [{timestamp}] ERROR: {message}{Colors.ENDC}")

def info_print(message, emoji="ℹ️"):
    """Красивая печать информации"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"{Colors.OKBLUE}{emoji} [{timestamp}] INFO: {message}{Colors.ENDC}")

def cache_print(message, emoji="💾"):
    """Красивая печать операций с кэшем"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"{Colors.HEADER}{emoji} [{timestamp}] CACHE: {message}{Colors.ENDC}")

def ai_print(message, emoji="🤖"):
    """Красивая печать AI операций"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"{Colors.OKCYAN}{emoji} [{timestamp}] AI: {message}{Colors.ENDC}")

def news_print(message, emoji="📰"):
    """Красивая печать новостей"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"{Colors.OKGREEN}{emoji} [{timestamp}] NEWS: {message}{Colors.ENDC}")

def markdown_to_html(text):
    """Заменяет **текст** на <b>текст</b> для Telegram HTML"""
    return re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)

class NewsBot:
    def __init__(self):
        self.application = Application.builder().token(BOT_TOKEN).build()
        self.ai_processor = AIProcessor()
        self.channel_reader = ChannelReader()
        
        # Кэш для новостей и сводок
        self.news_cache = []
        self.summary_cache = ""
        self.trends_cache = ""
        self.last_cache_update = None
        self.cache_file = "news_cache.json"
        
        # Настройки для большого количества каналов
        self.max_channels_per_request = 50  # Максимум каналов за раз
        self.max_messages_per_channel = 20   # Максимум сообщений с канала
        self.cache_duration = timedelta(hours=1)  # Время жизни кэша
        
        self.user_regions_file = "user_regions.json"
        self.user_regions = self.load_user_regions()
        self.support_enabled = True  # Флаг включения поддержки
        
        self.setup_handlers()
        self.load_cache()
    
    def load_cache(self):
        """Загрузка кэша из файла"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    self.news_cache = cache_data.get('news', [])
                    self.summary_cache = cache_data.get('summary', '')
                    self.trends_cache = cache_data.get('trends', '')
                    last_update = cache_data.get('last_update')
                    if last_update:
                        self.last_cache_update = datetime.fromisoformat(last_update)
                    cache_print(f"Кэш загружен: {len(self.news_cache)} новостей")
                    if self.last_cache_update:
                        cache_print(f"Время последнего обновления: {self.last_cache_update.strftime('%H:%M:%S')}")
            else:
                cache_print("Файл кэша не найден, начинаем с пустого кэша")
        except Exception as e:
            error_print(f"Ошибка загрузки кэша: {e}")
    
    def save_cache(self):
        """Сохранение кэша в файл"""
        try:
            cache_data = {
                'news': self.news_cache,
                'summary': self.summary_cache,
                'trends': self.trends_cache,
                'last_update': datetime.now().isoformat()
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            cache_print(f"Кэш сохранен: {len(self.news_cache)} новостей, сводка: {'есть' if self.summary_cache else 'нет'}, тренды: {'есть' if self.trends_cache else 'нет'}")
        except Exception as e:
            error_print(f"Ошибка сохранения кэша: {e}")
    
    def is_cache_valid(self):
        """Проверка актуальности кэша"""
        if not self.last_cache_update:
            cache_print("Кэш недействителен: нет времени обновления")
            return False
        is_valid = datetime.now() - self.last_cache_update < self.cache_duration
        cache_print(f"Кэш {'действителен' if is_valid else 'устарел'} (возраст: {datetime.now() - self.last_cache_update})")
        return is_valid
    
    async def get_cached_or_fresh_news(self, hours_back=6, force_refresh=False):
        """Получение новостей: из кэша или свежих"""
        # Если принудительное обновление или кэш недействителен
        if force_refresh or not self.is_cache_valid() or not self.news_cache:
            debug_print("Принудительное обновление или кэш недействителен, получаем свежие новости...")
            return await self._fetch_fresh_news(hours_back)
        
        # Кэш действителен, но проверим, есть ли новые новости
        try:
            debug_print("Кэш действителен, проверяем новые новости...")
            if not self.channel_reader.client:
                debug_print("Запускаем channel_reader...")
                await self.channel_reader.start()
            
            # Получаем свежие новости для сравнения
            fresh_messages = await self.channel_reader.get_all_channels_messages(hours_back=hours_back)
            
            if fresh_messages:
                # Сравниваем количество новостей
                if len(fresh_messages) > len(self.news_cache):
                    cache_print(f"Найдены новые новости! Кэш: {len(self.news_cache)}, свежие: {len(fresh_messages)}")
                    # Обновляем кэш
                    self.news_cache = fresh_messages
                    self.last_cache_update = datetime.now()
                    self.save_cache()
                    success_print(f"Кэш обновлен свежими новостями: {len(fresh_messages)}")
                    return fresh_messages
                else:
                    cache_print(f"Новых новостей нет, используем кэш: {len(self.news_cache)}")
                    return self.news_cache
            else:
                warning_print("Не удалось получить свежие новости, используем кэш")
                return self.news_cache
                
        except Exception as e:
            error_print(f"Ошибка проверки новых новостей: {e}")
            # В случае ошибки возвращаем кэш
            if self.news_cache:
                warning_print("Возвращаем кэш из-за ошибки")
                return self.news_cache
            return []
    
    async def _fetch_fresh_news(self, hours_back=6):
        """Получение свежих новостей"""
        try:
            debug_print(f"Запрашиваем свежие новости за последние {hours_back} часов...")
            if not self.channel_reader.client:
                debug_print("Запускаем channel_reader...")
                await self.channel_reader.start()
            
            messages = await self.channel_reader.get_all_channels_messages(hours_back=hours_back)
            
            if messages:
                # Обновляем кэш
                self.news_cache = messages
                self.last_cache_update = datetime.now()
                self.save_cache()
                success_print(f"Получены свежие новости: {len(messages)}")
                return messages
            elif self.news_cache:
                # Если новых нет, но есть кэшированные - возвращаем их
                warning_print("Новых новостей нет, возвращаем кэшированные")
                return self.news_cache
            else:
                warning_print("Новостей нет ни новых, ни кэшированных")
                return []
                
        except Exception as e:
            error_print(f"Ошибка получения новостей: {e}")
            # В случае ошибки возвращаем кэш если есть
            if self.news_cache:
                warning_print("Возвращаем кэш из-за ошибки")
                return self.news_cache
            return []
    
    def setup_handlers(self):
        """Настройка обработчиков команд и сообщений"""
        # Основные команды
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("menu", self.menu_command))
        
        # Команды новостей
        self.application.add_handler(CommandHandler("news", self.news_command))
        self.application.add_handler(CommandHandler("summary", self.summary_command))
        self.application.add_handler(CommandHandler("trends", self.trends_command))
        self.application.add_handler(CommandHandler("channels", self.channels_command))
        self.application.add_handler(CommandHandler("analyze", self.analyze_news_command))
        
        # Команды управления кэшем
        self.application.add_handler(CommandHandler("clear_cache", self.clear_cache_command))
        
        # Обработка нажатий на кнопки
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Новая команда /region
        self.application.add_handler(CommandHandler("region", self.region_command))
        self.application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.region_text_handler))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        info_print(f"Пользователь {user.first_name} ({user.id}) запустил бота")
        
        welcome_text = f"""
Привет, {user.first_name}! 👋

Я NEWS.AI - бот-агрегатор новостей с AI! 🤖📰

<b>Что я умею:</b>
• Читать Telegram каналы (оптимизировано для 100+ каналов)
• Создавать сводки новостей с помощью AI
• Анализировать тренды
• Оценивать уровень угроз в новостях
• Кэшировать данные для быстрого доступа
• Отправлять уведомления

<b>Команды:</b>
/news - Последние новости
/summary - AI сводка
/analyze - Анализ с оценкой угроз
/trends - Анализ трендов
/channels - Список каналов
/menu - Главное меню

<b>Новые возможности:</b>
💾 Кэширование на 1 час
🔄 Принудительное обновление
📄 Пагинация каналов
⚡ Оптимизация для большого количества каналов

Нажми /menu для доступа к функциям!
        """
        
        keyboard = [
            [InlineKeyboardButton("📰 Новости", callback_data="news")],
            [InlineKeyboardButton("🤖 AI Сводка", callback_data="summary")],
            [InlineKeyboardButton("🕐 Сводка за час", callback_data="summary_1h")],
            [InlineKeyboardButton("🔍 Анализ угроз", callback_data="analyze")],
            [InlineKeyboardButton("📊 Анализ трендов", callback_data="trends")],
            [InlineKeyboardButton("📺 Каналы", callback_data="channels")],
            [InlineKeyboardButton("ℹ️ Информация", callback_data="info")],
            [InlineKeyboardButton("❓ Помощь", callback_data="help")],
            [InlineKeyboardButton("💸 Донат", callback_data="donate")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        await self.show_help(update, context)
    
    async def show_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать справку"""
        help_text = """
❓ <b>Помощь по использованию</b>

<b>Команды новостей:</b>
📰 /news - Последние новости из каналов
🤖 /summary - AI сводка новостей
🔍 /analyze - Анализ новостей с оценкой угроз
📊 /trends - Анализ трендов
📺 /channels - Информация о каналах



<b>Как это работает:</b>
1. Бот читает указанные Telegram каналы
2. Обрабатывает новости с помощью AI (Claude 3.5)
3. Создает краткие сводки и анализирует тренды
4. Оценивает уровень угроз для каждой новости
5. Отправляет результаты в удобном формате

<b>Кэширование:</b>
💾 Новости кэшируются на 1 час для быстрого доступа
🔄 Кнопка "Обновить" принудительно обновляет данные
📊 Показывается источник данных (свежие/кэшированные)
⏰ Отображается время последнего обновления

<b>Оптимизация для большого количества каналов:</b>
📄 Пагинация каналов (5 каналов на страницу)
⚡ Ограничение запросов для стабильности
🔄 Умное кэширование для экономии ресурсов

<b>Уровни угроз:</b>
🟢 Низкий - обычные новости, события
🟠 Средний - происшествия, аварии
🔴 Высокий - атаки, катастрофы, кризисы

<b>Нужна дополнительная помощь?</b>
Нажмите кнопку "🛠️ Техподдержка" ниже.
        """
        
        keyboard = [
            [InlineKeyboardButton("🛠️ Техподдержка", callback_data="support")],
            [InlineKeyboardButton("🔙 Назад в меню", callback_data="menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def show_support(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать информацию о техподдержке"""
        if self.support_enabled:
            support_text = """
🛠️ <b>Служба поддержки</b>

Для связи с техподдержкой перейдите в нашего помощника:
👉 <b>@helpiqua_bot</b>

Откройте чат и напишите ваш вопрос — всё просто!
Ответит администратор или специалист поддержки.
            """
        else:
            support_text = """
🛠️ <b>Техподдержка временно недоступна</b>

⚠️ В данный момент служба поддержки находится на техническом обслуживании. Мы уже работаем над этим и скоро вернёмся!

🔍 Пока вы можете:
• Заглянуть в раздел «❓ Помощь» — там есть ответы на популярные вопросы
• Проверить подключение к интернету
• Попробовать перезапустить бота с помощью команды /start

🙏 Спасибо за понимание!

Для возврата в главное меню нажмите кнопку ниже.
            """
        keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(support_text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /menu"""
        user = update.effective_user
        info_print(f"Команда /menu от пользователя {user.first_name} ({user.id})")
        
        welcome_text = f"""
Привет, {user.first_name}! 👋

Я NEWS.AI - бот-агрегатор новостей с AI! 🤖📰

<b>Что я умею:</b>
• Читать Telegram каналы (оптимизировано для 100+ каналов)
• Создавать сводки новостей с помощью AI
• Анализировать тренды
• Оценивать уровень угроз в новостях
• Кэшировать данные для быстрого доступа
• Отправлять уведомления

<b>Команды:</b>
/news - Последние новости
/summary - AI сводка
/analyze - Анализ с оценкой угроз
/trends - Анализ трендов
/channels - Список каналов
/menu - Главное меню

<b>Новые возможности:</b>
💾 Кэширование на 1 час
🔄 Принудительное обновление
📄 Пагинация каналов
⚡ Оптимизация для большого количества каналов

Нажми /menu для доступа к функциям!
        """
        
        keyboard = [
            [InlineKeyboardButton("📰 Новости", callback_data="news")],
            [InlineKeyboardButton("🤖 AI Сводка", callback_data="summary")],
            [InlineKeyboardButton("🕐 Сводка за час", callback_data="summary_1h")],
            [InlineKeyboardButton("🔍 Анализ угроз", callback_data="analyze")],
            [InlineKeyboardButton("📊 Анализ трендов", callback_data="trends")],
            [InlineKeyboardButton("📺 Каналы", callback_data="channels")],
            [InlineKeyboardButton("ℹ️ Информация", callback_data="info")],
            [InlineKeyboardButton("❓ Помощь", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def news_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для получения последних новостей"""
        user = update.effective_user
        info_print(f"Команда /news от пользователя {user.first_name} ({user.id})")
        await update.message.reply_text("📰 Загружаю последние новости...")
        await self.get_latest_news(update, context)
    
    async def summary_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для создания AI сводки"""
        user = update.effective_user
        info_print(f"Команда /summary от пользователя {user.first_name} ({user.id})")
        await update.message.reply_text("🤖 Создаю AI сводку новостей...")
        await self.create_ai_summary(update, context, hours_back=12)
    
    async def trends_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для анализа трендов"""
        user = update.effective_user
        info_print(f"Команда /trends от пользователя {user.first_name} ({user.id})")
        await self.analyze_trends(update, context)
    
    async def channels_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для информации о каналах"""
        user = update.effective_user
        info_print(f"Команда /channels от пользователя {user.first_name} ({user.id})")
        await self.show_channels_info(update, context)
    
    async def analyze_news_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для анализа отдельных новостей с оценкой угроз"""
        user = update.effective_user
        info_print(f"Команда /analyze от пользователя {user.first_name} ({user.id})")
        await self.analyze_news(update, context)
    
    async def analyze_news(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Анализ угроз (заглушка)"""
        text = (
            "🔍 Анализ угроз\n\n"
            "⚠️ Функция в разработке\n\n"
            "Анализ угроз ещё недоступен и появится в следующих версиях бота.\n"
            "Мы уже работаем над тем, чтобы вы могли видеть оценку уровня угрозы для каждой новости.\n\n"
            "🛠 Ожидайте в будущих обновлениях!"
        )
        keyboard = [
            [InlineKeyboardButton("📰 Новости", callback_data="news")],
            [InlineKeyboardButton("🤖 AI Сводка", callback_data="summary")],
            [InlineKeyboardButton("🕐 Сводка за час", callback_data="summary_1h")],
            [InlineKeyboardButton("🔄 Обновить", callback_data="refresh_analyze")],
            [InlineKeyboardButton("🔙 Назад в меню", callback_data="menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def get_latest_news(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получить последние новости"""
        try:
            debug_print("Начинаем получение новостей...")
            
            # Получаем новости из кэша или свежие
            messages = await self.get_cached_or_fresh_news(hours_back=24)
            
            # ОТЛАДКА: выводим что получили
            debug_print(f"Получено {len(messages)} сообщений")
            if messages:
                for i, msg in enumerate(messages[:3], 1):
                    debug_print(f"  {i}. [{msg['channel']}] {msg['text'][:50]}...")
            else:
                debug_print("Сообщений НЕТ!")
            
            if not messages:
                debug_print("Нет сообщений, возвращаем пустой ответ")
                news_text = "📰 Новых сообщений не найдено.\n\nПопробуйте позже или проверьте подписки на каналы."
            else:
                debug_print("Формируем список новостей...")
                
                # Определяем источник данных
                cache_status = "🔄 Свежие новости" if not self.is_cache_valid() else "💾 Кэшированные новости"
                update_time = self.last_cache_update.strftime('%H:%M') if self.last_cache_update else "неизвестно"
                
                news_text = f"📰 <b>Последние новости</b> ({cache_status})\n"
                news_text += f"⏰ Обновлено: {update_time}\n"
                news_text += f"📰 Новостей: {len(messages)}\n\n"
                
                for i, msg in enumerate(messages[:10], 1):
                    channel = msg['channel']
                    text = msg['text'][:200] + "..." if len(msg['text']) > 200 else msg['text']
                    msg_time = datetime.fromisoformat(msg['date']).replace(tzinfo=None)
                    date = msg_time.strftime('%H:%M')
                    news_text += f"{i}. <b>{channel}</b> ({date})\n{text}\n\n"
            
            debug_print(f"Итоговый текст (первые 200 символов): {news_text[:200]}...")
            
            keyboard = [
                [InlineKeyboardButton("🤖 AI Сводка", callback_data="summary")],
                [InlineKeyboardButton("🕐 Сводка за час", callback_data="summary_1h")],
                [InlineKeyboardButton("🔍 Анализ угроз", callback_data="analyze")],
                [InlineKeyboardButton("🔄 Обновить", callback_data="refresh_news")],
                [InlineKeyboardButton("🔙 Назад в меню", callback_data="menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.callback_query:
                await update.callback_query.edit_message_text(news_text, reply_markup=reply_markup, parse_mode='HTML')
            else:
                await update.message.reply_text(news_text, reply_markup=reply_markup, parse_mode='HTML')
                
        except Exception as e:
            debug_print(f"Ошибка в get_latest_news: {e}")
            error_text = f"❌ Ошибка при получении новостей: {str(e)}"
            keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.callback_query:
                await update.callback_query.edit_message_text(error_text, reply_markup=reply_markup, parse_mode='HTML')
            else:
                await update.message.reply_text(error_text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def create_ai_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE, hours_back: int = 12):
        """Создать AI сводку"""
        try:
            ai_print("Начинаем создание AI сводки...")
            messages = await self.get_cached_or_fresh_news(hours_back=hours_back)
            if not messages:
                warning_print("Недостаточно новостей для создания сводки")
                text = "📰 Недостаточно новостей для создания сводки.\n\nПопробуйте позже или проверьте подписки на каналы."
                keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="menu")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                if update.callback_query:
                    await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
                else:
                    await update.message.reply_text(text, reply_markup=reply_markup)
                return
            # --- Новая логика автоудаления кэша старше 30 минут ---
            cache_expired = False
            if self.last_cache_update and hours_back == 12:
                age = datetime.now() - self.last_cache_update
                if age.total_seconds() > 1800:  # 30 минут
                    ai_print("Кэш сводки устарел (старше 30 минут), удаляем...")
                    self.summary_cache = ""
                    self.last_cache_update = None
                    self.save_cache()
                    cache_expired = True
            user_id = str(update.effective_user.id)
            user_region = context.user_data.get('region') or self.user_regions.get(user_id)
            print(f"[AI DEBUG] user_id={user_id}, user_region={user_region}")  # Дублируем регион в терминал
            if self.is_cache_valid() and self.summary_cache and not cache_expired and hours_back == 12:
                ai_print("Используем кэшированную сводку")
                summary = self.summary_cache
                cache_status = "💾 Кэшированная сводка"
            else:
                ai_print("Кэш сводки недействителен, создаем новую...")
                ai_print(f"Отправляем {len(messages)} новостей в AI для обработки...")
                # --- DEBUG: выводим prompt для AI ---
                from zoneinfo import ZoneInfo
                context_str = ""
                kyiv_tz = ZoneInfo("Europe/Kyiv")
                for i, msg in enumerate(messages[:200], 1):
                    try:
                        dt = datetime.fromisoformat(msg.get('date')).astimezone(kyiv_tz)
                        time_str = dt.strftime('%H:%M')
                    except Exception:
                        time_str = "??:??"
                    channel = msg.get('channel') or "?"
                    text = msg.get('text', '')[:200]
                    context_str += f"({time_str}, {channel}): {text}\n"
                region = user_region or "регион не выбран"
                # Вычислим time_range по полученным сообщениям
                hours = None
                if messages:
                    try:
                        dates = [datetime.fromisoformat(m.get('date')) for m in messages if m.get('date')]
                        if dates:
                            min_date = min(dates)
                            max_date = max(dates)
                            delta = max_date - min_date
                            hours = int(delta.total_seconds() // 3600)
                    except Exception:
                        hours = None
                if hours is not None and hours <= 1:
                    time_range = "30–60 минут"
                elif hours is not None:
                    time_range = f"{hours} часов"
                else:
                    time_range = "несколько часов"
                prompt = f"""
Ты — ИИ, создающий строго структурированную сводку новостей для одного региона Украины.

🎯 Цель:
Сформировать короткую, точную и актуальную сводку по указанному региону (г. {region}) и общей ситуации по стране, используя **только свежие события за последние {time_range} минут**.

📌 Правила:

1. Используй **только переданные новости**. Не придумывай события.  
2. Включай **только события, которые происходят в г. {region}**. Игнорируй все новости из других областей.  
3. Исключай **завершённые или устаревшие события**, а также **рекламу, акции, праздники и нерелевантные сообщения**.  
   Примеры игнорируемого: акции магазинов, розыгрыши, обзоры цен, текстиль, подарки и т.п.  
4. Сортируй события по времени (новее — выше), затем по числу упоминаний (часто упоминаемые → выше).  
5. Включай только **важные события**: атаки, БПЛА, обстріли, аварії, критичні події.  
6. Если в регионе **нет актуальных событий**, выводи только:
📍 Главные события в регионе:  
• Нет актуальных событий на данный момент.  
7. Не дублируй блоки. Раздел “📍 Главные события в регионе” должен быть один раз.  
8. Обязательно добавь раздел "🇺🇦 Общая ситуация по стране" с 2–5 важными событиями.  
9. Строго соблюдай формат, сжимай длинные новости до одной строки без потери смысла.  

⸻

📍 Формат вывода (строго соблюдай):

📊 Уровень угрозы: [🟢 / 🟡 / 🟠 / 🔴]  

📍 Главные события в регионе:  
• [событие 1]  
• [событие 2]  
• [событие 3]  

🇺🇦 Общая ситуация по стране:  
• [событие 1]  
• [событие 2]  
• [событие 3]  

📌 Регион: {region}

⸻

📥 Вставь сюда новости и события для анализа:
{context_str}
"""
                debug_print(f"PROMPT ДЛЯ AI (регион: {region}):\n{prompt}\n\nВот новости:\n{context_str}")
                # --- END DEBUG ---
                summary = await self.ai_processor.create_summary(messages, user_region)
                ai_print("AI сводка создана успешно")
                if hours_back == 12:
                    self.summary_cache = summary
                    self.last_cache_update = datetime.now()
                    self.save_cache()
                cache_status = "🔄 Свежая сводка"
            update_time = datetime.now().strftime('%H:%M')
            summary_with_info = f"🤖 **AI Сводка новостей** ({cache_status})\n"
            summary_with_info += f"⏰ Обновлено: {update_time}\n"
            summary_with_info += f"📰 Новостей: {len(messages)}\n"
            user_region_str = user_region or "регион не выбран"
            summary_with_info += f"📰 СВОДКА ДЛЯ: {user_region_str}\n"
            summary_with_info += summary
            # Заменяем **текст** на <b>текст</b> для Telegram
            summary_with_info = markdown_to_html(summary_with_info)
            keyboard = [
                [InlineKeyboardButton("📊 Тренды", callback_data="trends")],
                [InlineKeyboardButton("📰 Новости", callback_data="news")],
                [InlineKeyboardButton("🕐 Сводка за час", callback_data="summary_1h")],
                [InlineKeyboardButton("🔄 Обновить", callback_data="refresh_summary")],
                [InlineKeyboardButton("🔙 Назад в меню", callback_data="menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            if update.callback_query:
                await update.callback_query.edit_message_text(summary_with_info, reply_markup=reply_markup)
            else:
                await update.message.reply_text(summary_with_info, reply_markup=reply_markup)
        except Exception as e:
            error_print(f"Ошибка при создании сводки: {e}")
            error_text = f"❌ Ошибка при создании сводки: {str(e)}"
            keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            if update.callback_query:
                await update.callback_query.edit_message_text(error_text, reply_markup=reply_markup)
            else:
                await update.message.reply_text(error_text, reply_markup=reply_markup)
    
    async def analyze_trends(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Анализ трендов (заглушка)"""
        text = (
            "📊 Анализ трендов\n\n"
            "⚠️ Функция в разработке\n\n"
            "Анализ трендов ещё недоступен и появится в следующих версиях бота.\n"
            "Мы уже работаем над тем, чтобы вы могли видеть, какие события повторяются чаще всего и как меняется информационная картина.\n\n"
            "🛠 Ожидайте в будущих обновлениях!"
        )
        keyboard = [
            [InlineKeyboardButton("🤖 AI Сводка", callback_data="summary")],
            [InlineKeyboardButton("📰 Новости", callback_data="news")],
            [InlineKeyboardButton("🕐 Сводка за час", callback_data="summary_1h")],
            [InlineKeyboardButton("🔄 Обновить", callback_data="refresh_trends")],
            [InlineKeyboardButton("🔙 Назад в меню", callback_data="menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def show_channels_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать информацию о каналах, на которые подписан аккаунт"""
        try:
            if not self.channel_reader.client:
                await self.channel_reader.start()
            
            channels = self.channel_reader.channels
            
            # Получаем номер страницы из контекста
            page = context.user_data.get('channels_page', 0)
            channels_per_page = 5  # Показываем 5 каналов на страницу
            
            # Разбиваем каналы на страницы
            total_pages = (len(channels) + channels_per_page - 1) // channels_per_page
            start_idx = page * channels_per_page
            end_idx = min(start_idx + channels_per_page, len(channels))
            current_channels = channels[start_idx:end_idx]
            
            channels_text = f"📺 **Каналы, на которые подписан аккаунт:**\n"
            channels_text += f"📊 Всего каналов: {len(channels)}\n"
            channels_text += f"📄 Страница {page + 1} из {total_pages}\n\n"
            
            for i, channel in enumerate(current_channels, start_idx + 1):
                info = await self.channel_reader.get_channel_info(channel)
                if info:
                    channels_text += f"📰 **{info['title']}**\n"
                    participants = info.get('participants_count', 0) or 0
                    username = info.get('username', 'unknown')
                    channels_text += f"👥 Подписчиков: {participants:,}\n"
                    channels_text += f"🔗 @{username}\n\n"
                else:
                    channels_text += f"❌ {getattr(channel, 'username', getattr(channel, 'title', 'unknown'))} - недоступен\n\n"
            
            # Создаем кнопки навигации
            keyboard = []
            
            # Кнопки навигации по страницам
            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data="channels_prev"))
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data="channels_next"))
            
            if nav_buttons:
                keyboard.append(nav_buttons)
            
            # Основные кнопки
            keyboard.extend([
                [InlineKeyboardButton("📬 Предложить канал", callback_data="suggest_channel")],
                [InlineKeyboardButton("📰 Новости", callback_data="news")],
                [InlineKeyboardButton("🔙 Назад в меню", callback_data="menu")]
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.callback_query:
                await update.callback_query.edit_message_text(channels_text, reply_markup=reply_markup)
            else:
                await update.message.reply_text(channels_text, reply_markup=reply_markup)
                
        except Exception as e:
            error_text = f"❌ Ошибка при получении информации о каналах: {str(e)}"
            keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            if update.callback_query:
                await update.callback_query.edit_message_text(error_text, reply_markup=reply_markup)
            else:
                await update.message.reply_text(error_text, reply_markup=reply_markup)
    
    async def show_suggest_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать форму предложения канала"""
        suggest_text = """
📬 **Предложить канал**

Если вы знаете Telegram-канал, с которого стоит брать новости — просто отправьте его сюда сообщением.
Например:
https://t.me/example_channel

Мы проверим его и, при необходимости, добавим в список мониторинга.
        """
        
        keyboard = [[InlineKeyboardButton("🔙 Назад к каналам", callback_data="channels")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Устанавливаем флаг ожидания предложения канала
        context.user_data['waiting_for_channel_suggestion'] = True
        
        if update.callback_query:
            await update.callback_query.edit_message_text(suggest_text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.message.reply_text(suggest_text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        debug_print(f"Нажата кнопка: {query.data}")
        if query.data == "menu":
            debug_print("Переход в главное меню")
            user = update.effective_user
            welcome_text = f"""
Привет, {user.first_name}! 👋

Я NEWS.AI - бот-агрегатор новостей с AI! 🤖📰

<b>Что я умею:</b>
• Читать Telegram каналы (оптимизировано для 100+ каналов)
• Создавать сводки новостей с помощью AI
• Анализировать тренды
• Оценивать уровень угроз в новостях
• Кэшировать данные для быстрого доступа
• Отправлять уведомления

<b>Команды:</b>
/news - Последние новости
/summary - AI сводка
/analyze - Анализ с оценкой угроз
/trends - Анализ трендов
/channels - Список каналов
/menu - Главное меню

<b>Новые возможности:</b>
💾 Кэширование на 1 час
🔄 Принудительное обновление
📄 Пагинация каналов
⚡ Оптимизация для большого количества каналов

Нажми /menu для доступа к функциям!
            """
            
            keyboard = [
                [InlineKeyboardButton("📰 Новости", callback_data="news")],
                [InlineKeyboardButton("🤖 AI Сводка", callback_data="summary")],
                [InlineKeyboardButton("🕐 Сводка за час", callback_data="summary_1h")],
                [InlineKeyboardButton("🔍 Анализ угроз", callback_data="analyze")],
                [InlineKeyboardButton("📊 Анализ трендов", callback_data="trends")],
                [InlineKeyboardButton("📺 Каналы", callback_data="channels")],
                [InlineKeyboardButton("ℹ️ Информация", callback_data="info")],
                [InlineKeyboardButton("❓ Помощь", callback_data="help")],
                [InlineKeyboardButton("💸 Донат", callback_data="donate")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')
        elif query.data == "help":
            debug_print("Показываем справку")
            await self.show_help(update, context)
        elif query.data == "support":
            debug_print("Показываем техподдержку")
            await self.show_support(update, context)
        elif query.data == "info":
            debug_print("Показываем информацию о боте")
            await self.show_info(update, context)
        elif query.data == "admin_panel":
            debug_print("Открытие секретной панели")
            await self.show_admin_panel(update, context)
        elif query.data == "admin_broadcast":
            debug_print("Открытие меню рассылок")
            await self.show_broadcast_menu(update, context)
        elif query.data == "broadcast_test":
            debug_print("Ожидание текста для тестовой рассылки")
            context.user_data['broadcast_mode'] = 'test'
            await update.callback_query.edit_message_text(
                "🧪 Введите текст тестовой рассылки (отправьте следующим сообщением):",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_broadcast")]])
            )
        elif query.data == "broadcast_all":
            debug_print("Ожидание текста для рассылки всем пользователям")
            context.user_data['broadcast_mode'] = 'all'
            await update.callback_query.edit_message_text(
                "📤 Введите текст рассылки для всех пользователей:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_broadcast")]])
            )
        elif query.data == "broadcast_region":
            debug_print("Выбор региона для рассылки по регионам")
            context.user_data['broadcast_mode'] = 'region_select'
            regions = [
                "Винницкая область", "Волынская область", "Днепропетровская область",
                "Донецкая область", "Житомирская область", "Закарпатская область",
                "Запорожская область", "Ивано-Франковская область", "Киевская область",
                "Кировоградская область", "Львовская область", "Николаевская область",
                "Одесская область", "Полтавская область", "Ровенская область",
                "Сумская область", "Тернопольская область", "Харьковская область",
                "Херсонская область", "Хмельницкая область", "Черкасская область",
                "Черниговская область", "Черновицкая область", "г. Киев"
            ]
            keyboard = [[InlineKeyboardButton(region, callback_data=f"broadcast_region_{region}")] for region in regions]
            keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_broadcast")])
            await update.callback_query.edit_message_text(
                "🎯 Выберите регион для рассылки:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        elif query.data.startswith("broadcast_region_"):
            region = query.data.replace("broadcast_region_", "")
            debug_print(f"Ожидание текста для рассылки по региону: {region}")
            context.user_data['broadcast_mode'] = 'region'
            context.user_data['broadcast_region'] = region
            await update.callback_query.edit_message_text(
                f"🎯 Введите текст рассылки для региона: {region}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_broadcast")]])
            )
        elif query.data == "news":
            debug_print("Запрос новостей")
            await self.get_latest_news(update, context)
        elif query.data == "summary":
            debug_print("Запрос AI сводки (12ч)")
            await self.create_ai_summary(update, context, hours_back=12)
        elif query.data == "summary_1h":
            debug_print("Запрос AI сводки за 1 час")
            await self.create_ai_summary(update, context, hours_back=1)
        elif query.data == "trends":
            debug_print("Запрос анализа трендов")
            await self.analyze_trends(update, context)
        elif query.data == "channels":
            debug_print("Запрос информации о каналах")
            await self.show_channels_info(update, context)
        elif query.data == "analyze":
            debug_print("Запрос анализа новостей с угрозами")
            await self.analyze_news(update, context)
        # Кнопки обновления (принудительно обновляют кэш)
        elif query.data == "refresh_news":
            debug_print("Принудительное обновление новостей")
            # Сбрасываем кэш для принудительного обновления
            self.last_cache_update = None
            await self.get_latest_news(update, context)
        elif query.data == "refresh_summary":
            debug_print("Принудительное обновление сводки")
            # Сбрасываем кэш сводки
            self.summary_cache = ""
            self.last_cache_update = None
            await self.create_ai_summary(update, context, hours_back=12)
        elif query.data == "refresh_trends":
            debug_print("Принудительное обновление трендов")
            # Сбрасываем кэш трендов
            self.trends_cache = ""
            self.last_cache_update = None
            await self.analyze_trends(update, context)
        elif query.data == "refresh_analyze":
            debug_print("Принудительное обновление анализа")
            # Сбрасываем кэш для принудительного обновления анализа
            self.last_cache_update = None
            await self.analyze_news(update, context)
        # Навигация по каналам
        elif query.data == "channels_prev":
            page = context.user_data.get('channels_page', 0)
            if page > 0:
                context.user_data['channels_page'] = page - 1
                debug_print(f"Переход на предыдущую страницу каналов: {page - 1}")
            await self.show_channels_info(update, context)
        elif query.data == "channels_next":
            page = context.user_data.get('channels_page', 0)
            context.user_data['channels_page'] = page + 1
            debug_print(f"Переход на следующую страницу каналов: {page + 1}")
            await self.show_channels_info(update, context)
        elif query.data == "suggest_channel":
            debug_print("Запрос предложения канала")
            await self.show_suggest_channel(update, context)
        elif query.data == "channels":
            debug_print("Возврат к списку каналов")
            await self.show_channels_info(update, context)
        elif query.data == "donate":
            debug_print("Запрос страницы доната")
            await self.show_donate(update, context)
        elif query.data == "toggle_support":
            if self.support_enabled:
                self.disable_support()
                debug_print("Техподдержка отключена через админ-панель")
            else:
                self.enable_support()
                debug_print("Техподдержка включена через админ-панель")
            await self.show_admin_panel(update, context)
    
    async def show_admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать главное меню секретной панели"""
        text = "🪄 **Секретная панель разработчика**\n\nВыберите раздел:"
        support_status = "Включить поддержку" if not self.support_enabled else "Отключить поддержку"
        keyboard = [
            [InlineKeyboardButton("📨 Рассылки", callback_data="admin_broadcast")],
            [InlineKeyboardButton("📈 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton("📊 Логи", callback_data="admin_logs")],
            [InlineKeyboardButton("🖥 Мониторинг", callback_data="admin_monitor")],
            [InlineKeyboardButton("⚡ Быстрые действия", callback_data="admin_quick")],
            [InlineKeyboardButton("👤 Пользователи", callback_data="admin_users")],
            [InlineKeyboardButton("📺 Каналы", callback_data="admin_channels")],
            [InlineKeyboardButton("💾 Экспорт/импорт", callback_data="admin_export")],
            [InlineKeyboardButton("🧪 Песочница AI", callback_data="admin_sandbox")],
            [InlineKeyboardButton(f"🛠️ {support_status}", callback_data="toggle_support")],
            [InlineKeyboardButton("🔙 Назад", callback_data="info")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def show_broadcast_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать меню рассылок в секретной панели"""
        text = "📨 **Меню рассылок**\n\nВыберите тип рассылки:"
        keyboard = [
            [InlineKeyboardButton("📤 Всем пользователям", callback_data="broadcast_all")],
            [InlineKeyboardButton("🎯 По регионам", callback_data="broadcast_region")],
            [InlineKeyboardButton("🧪 Тестовая себе", callback_data="broadcast_test")],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def show_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать информацию о боте"""
        import platform
        
        # Получаем количество каналов
        channels_count = len(self.channel_reader.channels) if self.channel_reader.channels else 0
        
        # Информация о кэше
        cache_info = "✅ Активен" if self.is_cache_valid() else "❌ Устарел"
        cache_time = self.last_cache_update.strftime('%H:%M') if self.last_cache_update else "нет"
        
        info_text = f"""
ℹ️ <b>Информация о NEWS.AI</b>

🤖 <b>Версия:</b> 0.9.4 (NEWS.AI)
🐍 <b>Python:</b> {platform.python_version()}
📅 <b>Дата:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}

<b>Технологии:</b>
• python-telegram-bot 20.7
• Telethon (чтение каналов)
• Groq API (Llama/Meta)
• Асинхронная обработка
• Кэширование данных

<b>Мониторинг каналов:</b> {channels_count} каналов
<b>AI модель:</b> {getattr(self.ai_processor, 'model', 'неизвестно')}
<b>Кэш:</b> {cache_info} (обновлен: {cache_time})
<b>Время жизни кэша:</b> 1 час
<b>Максимум каналов за раз:</b> {self.max_channels_per_request}

<b>Новые возможности:</b>
• 💾 Кэширование новостей и сводок
• 🔄 Принудительное обновление
• 📄 Пагинация для большого количества каналов
• ⚡ Оптимизация для 100+ каналов
• 📊 Информация о времени обновления

<b>Разработчик:</b> Разработчик остался анонимным
        """
        
        keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="menu")]]
        # Добавляем секретную кнопку только для ADMIN_ID
        user_id = update.effective_user.id if update.effective_user else None
        if str(user_id) == str(ADMIN_ID):
            keyboard.insert(0, [InlineKeyboardButton("🪄 Волшебная панель", callback_data="admin_panel")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(info_text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def clear_cache_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для очистки кэша"""
        try:
            cache_print("Очистка кэша...")
            
            # Очищаем кэш
            self.news_cache = []
            self.summary_cache = ""
            self.trends_cache = ""
            self.last_cache_update = None
            
            # Удаляем файл кэша
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
                cache_print("Файл кэша удален")
            
            success_print("Кэш полностью очищен")
            text = "🗑️ **Кэш очищен!**\n\nВсе кэшированные данные удалены. При следующем запросе будут загружены свежие новости."
            
            keyboard = [
                [InlineKeyboardButton("📰 Новости", callback_data="news")],
                [InlineKeyboardButton("🤖 AI Сводка", callback_data="summary")],
                [InlineKeyboardButton("🔙 Назад в меню", callback_data="menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(text, reply_markup=reply_markup)
            
        except Exception as e:
            error_print(f"Ошибка при очистке кэша: {e}")
            error_text = f"❌ Ошибка при очистке кэша: {str(e)}"
            await update.message.reply_text(error_text)
    
    async def region_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /region - выбор региона через обычные кнопки"""
        regions = [
            "Винницкая область", "Волынская область", "Днепропетровская область",
            "Донецкая область", "Житомирская область", "Закарпатская область",
            "Запорожская область", "Ивано-Франковская область", "Киевская область",
            "Кировоградская область", "Львовская область", "Николаевская область",
            "Одесская область", "Полтавская область", "Ровенская область",
            "Сумская область", "Тернопольская область", "Харьковская область",
            "Херсонская область", "Хмельницкая область", "Черкасская область",
            "Черниговская область", "Черновицкая область", "г. Киев"
        ]
        # Разбиваем по 3 в ряд
        keyboard = [regions[i:i+3] for i in range(0, len(regions), 3)]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        user_id = str(update.effective_user.id)
        # Если регион уже выбран, показываем его
        current_region = self.user_regions.get(user_id)
        if current_region:
            await update.message.reply_text(
                f"Ваш текущий регион: {current_region}\n\nЧтобы изменить, выберите новый регион:",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                "Пожалуйста, выберите ваш регион:",
                reply_markup=reply_markup
            )
    
    async def region_text_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора региона через обычные кнопки и предложений каналов"""
        user_text = update.message.text.strip()
        user_id = str(update.effective_user.id)
        
        # Проверяем, ожидается ли предложение канала
        if context.user_data.get('waiting_for_channel_suggestion'):
            await self.handle_channel_suggestion(update, context, user_text)
            return
        
        # Проверяем режим рассылки
        if context.user_data.get('broadcast_mode') == 'test':
            del context.user_data['broadcast_mode']
            await update.message.reply_text(
                "🧪 Тестовая рассылка отправлена только вам!",
                reply_markup=ReplyKeyboardRemove()
            )
            await update.message.reply_text(update.message.text)
            await self.show_broadcast_menu(update, context)
            return
        if context.user_data.get('broadcast_mode') == 'all':
            del context.user_data['broadcast_mode']
            count = 0
            for user_id in self.user_regions.keys():
                try:
                    await self.application.bot.send_message(chat_id=int(user_id), text=update.message.text)
                    count += 1
                except Exception as e:
                    debug_print(f"Не удалось отправить сообщение {user_id}: {e}")
            await update.message.reply_text(f"📤 Рассылка отправлена {count} пользователям.", reply_markup=ReplyKeyboardRemove())
            await self.show_broadcast_menu(update, context)
            return
        if context.user_data.get('broadcast_mode') == 'region':
            region = context.user_data.get('broadcast_region')
            del context.user_data['broadcast_mode']
            del context.user_data['broadcast_region']
            count = 0
            for user_id, user_region in self.user_regions.items():
                # Лог для отладки
                print(f"user_id={user_id}, user_region={user_region}, рассылка для: {region}")
                # Сравниваем без учёта регистра и пробелов
                if user_region and region and user_region.strip().lower() == region.strip().lower():
                    try:
                        await self.application.bot.send_message(chat_id=int(user_id), text=update.message.text)
                        count += 1
                    except Exception as e:
                        debug_print(f"Не удалось отправить сообщение {user_id}: {e}")
            await update.message.reply_text(f"🎯 Рассылка по региону '{region}' отправлена {count} пользователям.", reply_markup=ReplyKeyboardRemove())
            await self.show_broadcast_menu(update, context)
            return
        
        # Обработка выбора региона
        regions = [
            "Винницкая область", "Волынская область", "Днепропетровская область",
            "Донецкая область", "Житомирская область", "Закарпатская область",
            "Запорожская область", "Ивано-Франковская область", "Киевская область",
            "Кировоградская область", "Львовская область", "Николаевская область",
            "Одесская область", "Полтавская область", "Ровенская область",
            "Сумская область", "Тернопольская область", "Харьковская область",
            "Херсонская область", "Хмельницкая область", "Черкасская область",
            "Черниговская область", "Черновицкая область", "г. Киев"
        ]
        
        if user_text in regions:
            context.user_data['region'] = user_text
            self.user_regions[user_id] = user_text
            self.save_user_regions()
            await update.message.reply_text(
                f"Ваш регион сохранён: {user_text}\n\nЧтобы изменить, используйте /region.",
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            await update.message.reply_text(
                "Пожалуйста, выберите регион только из списка кнопок.",
            )
    
    async def handle_channel_suggestion(self, update: Update, context: ContextTypes.DEFAULT_TYPE, channel_text: str):
        """Обработка предложения канала"""
        try:
            user = update.effective_user
            user_id = user.id
            user_name = user.first_name or user.username or "Неизвестный пользователь"
            
            # Убираем флаг ожидания
            del context.user_data['waiting_for_channel_suggestion']
            
            # Проверяем, что это похоже на ссылку на канал
            if not any(pattern in channel_text.lower() for pattern in ['t.me/', 'telegram.me/', '@']):
                await update.message.reply_text(
                    "❌ Это не похоже на ссылку на Telegram-канал.\n\n"
                    "Пожалуйста, отправьте ссылку в формате:\n"
                    "• https://t.me/channel_name\n"
                    "• @channel_name\n\n"
                    "Попробуйте ещё раз или нажмите кнопку «Назад к каналам».",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад к каналам", callback_data="channels")]])
                )
                return
            
            # Отправляем предложение админу
            admin_message = f"""
📬 **Новое предложение канала**

👤 **От пользователя:**
• ID: {user_id}
• Имя: {user_name}
• Username: @{user.username if user.username else 'нет'}

📺 **Предложенный канал:**
{channel_text}

⏰ **Время:** {datetime.now().strftime('%d.%m.%Y %H:%M')}
            """
            
            try:
                # Отправляем админу
                await self.application.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=admin_message,
                    parse_mode='HTML'
                )
                info_print(f"Предложение канала от {user_name} ({user_id}) отправлено админу")
            except Exception as e:
                error_print(f"Ошибка отправки предложения админу: {e}")
            
            # Отправляем подтверждение пользователю
            success_text = """
Спасибо! 🙌
Ваш канал принят. Мы рассмотрим его и при необходимости добавим в список мониторинга.

Если хотите предложить ещё — просто отправьте ссылку на следующий канал.
            """
            
            keyboard = [
                [InlineKeyboardButton("📬 Предложить ещё", callback_data="suggest_channel")],
                [InlineKeyboardButton("🔙 Назад к каналам", callback_data="channels")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(success_text, reply_markup=reply_markup)
            
        except Exception as e:
            error_print(f"Ошибка обработки предложения канала: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при обработке вашего предложения.\n\nПопробуйте позже или обратитесь в поддержку.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад к каналам", callback_data="channels")]])
            )
    
    async def show_donate(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать страницу доната"""
        donate_link = f"\n🔗 **Ссылка для доната:**\n{DONATE_URL}\n" if DONATE_URL else ""
        donate_text = f"""
💸 **Поддержка проекта**

Если бот вам помогает — вы можете поддержать его развитие 🙌
Автор работает ночами, а нейросеть требует ресурсов 🧠⚡️
{donate_link}
Спасибо за вашу поддержку!
        """
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(donate_text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.message.reply_text(donate_text, reply_markup=reply_markup, parse_mode='HTML')
    
    def load_user_regions(self):
        """Загрузка регионов пользователей из файла"""
        if os.path.exists(self.user_regions_file):
            try:
                with open(self.user_regions_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                warning_print(f"Ошибка загрузки user_regions: {e}")
                return {}
        return {}

    def save_user_regions(self):
        """Сохранение регионов пользователей в файл"""
        try:
            with open(self.user_regions_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_regions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            warning_print(f"Ошибка сохранения user_regions: {e}")
    
    def enable_support(self):
        self.support_enabled = True
    def disable_support(self):
        self.support_enabled = False
    
    def run(self):
        """Запуск бота"""
        info_print("🚀 Запуск NEWS.AI бота...")
        info_print(f"🤖 Версия: 0.9.4 (NEWS.AI)")
        info_print(f"💾 Кэширование: включено (1 час)")
        info_print(f"📊 Оптимизация: для 100+ каналов")
        info_print(f"🎯 Режим: отладка с цветными логами")
        
        # Показываем информацию о кэше при запуске
        if self.news_cache:
            cache_print(f"Загружен кэш: {len(self.news_cache)} новостей")
        else:
            cache_print("Кэш пуст, будет создан при первом запросе")
        
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    bot = NewsBot()
    bot.run() 