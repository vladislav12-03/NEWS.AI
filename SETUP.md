# 🚀 Настройка бота-агрегатора новостей

## 📋 Что нужно настроить:

### 1. **Скопируйте шаблон окружения**
```bash
cp .env.example .env
```

### 2. **Telegram Bot Token** 🤖
1. Найдите [@BotFather](https://t.me/BotFather) в Telegram
2. Создайте бота командой `/newbot`
3. Добавьте токен в `.env`:
   ```
   BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ```

### 3. **Admin ID** 👤
1. Узнайте свой ID через [@userinfobot](https://t.me/userinfobot)
2. Добавьте в `.env`:
   ```
   ADMIN_ID=123456789
   ```

### 4. **Groq API Key** 🔑
1. Зайдите на [console.groq.com](https://console.groq.com)
2. Создайте API ключ
3. Добавьте в `.env`:
   ```
   GROQ_API_KEY=gsk_your_actual_key_here
   ```

### 5. **Telegram API для чтения каналов** 📱
1. Зайдите на [my.telegram.org](https://my.telegram.org)
2. Перейдите в "API development tools"
3. Создайте приложение и скопируйте **API ID** и **API Hash**
4. Добавьте в `.env`:
   ```
   TELEGRAM_API_ID=12345678
   TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
   TELEGRAM_PHONE=+380000000000
   ```

### 6. **Ссылка на донат (необязательно)** 💸
```
DONATE_URL=https://example.com/donate
```

## 🔧 Запуск:

1. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Настройте все переменные в `.env`**

3. **Запустите бота:**
   ```bash
   python bot.py
   ```

## 🎯 Функции бота:

- **📰 /news** - Последние новости из каналов
- **🤖 /summary** - AI сводка новостей
- **📊 /trends** - Анализ трендов
- **📺 /channels** - Информация о каналах

## ⚠️ Важные моменты:

1. **Telegram аккаунт** должен быть подписан на каналы для чтения
2. **Groq** имеет лимиты на бесплатном плане
3. **Каналы** должны быть публичными или аккаунт должен быть участником
4. Файл `.env` не попадает в Git — используйте `.env.example` как шаблон

## 🐛 Решение проблем:

### Ошибка "Channel not found"
- Проверьте, что аккаунт подписан на каналы

### Ошибка "API key invalid"
- Проверьте правильность GROQ_API_KEY

### Ошибка "Phone number invalid"
- Используйте формат: `+380000000000`
- Убедитесь, что номер привязан к Telegram

---

**Удачи с настройкой! 🚀**
