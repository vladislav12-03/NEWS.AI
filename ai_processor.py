import json
from typing import List, Dict
import requests
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from config import GROQ_API_KEY, GROQ_API_URL, GROQ_MODEL

class AIProcessor:
    def __init__(self):
        self.api_key = GROQ_API_KEY
        self.base_url = GROQ_API_URL
        self.model = GROQ_MODEL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def create_summary(self, messages: list, user_region: str = None) -> str:
        """Создает сводку новостей с учетом региона пользователя и уровня угрозы"""
        if not messages:
            return "📰 Нет новостей для создания сводки."
        
        try:
            # Формируем контекст из последних сообщений (до 200)
            context = ""
            kyiv_tz = ZoneInfo("Europe/Kyiv")
            for i, msg in enumerate(messages[:200], 1):
                # Получаем время и канал
                try:
                    dt = datetime.fromisoformat(msg.get('date')).astimezone(kyiv_tz)
                    time_str = dt.strftime('%H:%M')
                except Exception:
                    time_str = "??:??"
                channel = msg.get('channel') or "?"
                text = msg.get('text', '')[:200]
                context += f"({time_str}, {channel}): {text}\n"
            
            region = user_region or "регион не выбран"
            # Определяем диапазон времени для подстановки
            hours = None
            if messages:
                try:
                    from datetime import datetime
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
{context}
"""
            
            data = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1000,
                "temperature": 0.5
            }
            
            # Увеличиваем таймаут до 150 секунд и добавляем retry
            for attempt in range(3):
                try:
                    response = requests.post(
                        self.base_url,
                        headers=self.headers,
                        json=data,
                        timeout=150  # 2.5 минуты
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        summary = result['choices'][0]['message']['content'].strip()
                        return summary
                    else:
                        error_text = response.text
                        return f"❌ Ошибка AI обработки: {response.status_code} - {error_text}"
                        
                except requests.exceptions.Timeout:
                    if attempt < 2:
                        continue
                    return "❌ Таймаут соединения с AI сервисом. Попробуйте позже."
                except requests.exceptions.ConnectionError as e:
                    if attempt < 2:
                        continue
                    return f"❌ Ошибка соединения с AI сервисом: {str(e)}"
                except Exception as e:
                    if attempt < 2:
                        continue
                    return f"❌ Ошибка AI обработки: {str(e)}"
            
            return "❌ Не удалось подключиться к AI сервису после нескольких попыток."
            
        except Exception as e:
            return f"❌ Ошибка AI обработки: {str(e)}"
    
    def clean_markdown(self, text: str) -> str:
        """Очищает текст от проблемных символов для Telegram Markdown"""
        # Убираем двойные звездочки в середине слов
        text = re.sub(r'(?<!\*)\*\*(?!\*)', '', text)
        text = re.sub(r'(?<!\*)\*(?!\*)', '', text)
        
        # Убираем подчеркивания
        text = text.replace('_', '')
        
        # Убираем квадратные скобки без закрывающих
        text = re.sub(r'\[([^\]]*)$', r'\1', text)
        text = re.sub(r'^([^\[]*)\]', r'\1', text)
        
        # Убираем круглые скобки без закрывающих
        text = re.sub(r'\(([^)]*)$', r'\1', text)
        text = re.sub(r'^([^(]*)\)', r'\1', text)
        
        # Убираем обратные кавычки
        text = text.replace('`', '')
        
        # Убираем символы # в начале строк
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
        
        return text
    
    async def analyze_news_with_threat_assessment(self, news_text: str) -> str:
        """Анализирует новость с оценкой угрозы"""
        try:
            prompt = f"""
Проанализируй следующую новость и оцени уровень угрозы:

{news_text}

Структура ответа:
1. Краткое описание события
2. Оценка уровня угрозы (Низкий/Средний/Высокий)
3. Обоснование оценки
4. Потенциальные последствия

Используй простой текст без разметки.
"""
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "meta-llama/llama-4-scout-17b-16e-instruct",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 500,
                "temperature": 0.5
            }
            
            response = requests.post(
                self.base_url,
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                analysis = result['choices'][0]['message']['content'].strip()
                
                # Очищаем от проблемных символов
                analysis = self.clean_markdown(analysis)
                
                return analysis
            else:
                error_text = response.text
                return f"❌ Ошибка анализа: {response.status_code} - {error_text}"
                
        except Exception as e:
            return f"❌ Ошибка при анализе новости: {str(e)}"
    
    async def analyze_trends(self, messages: List[Dict]) -> str:
        """Анализирует тренды в новостях"""
        if not messages:
            return "📊 Недостаточно данных для анализа трендов."
        
        try:
            # Формируем контекст
            context = ""
            for i, msg in enumerate(messages[:15], 1):
                context += f"{i}. {msg.get('text', '')[:150]}...\n"
            
            prompt = f"""
Проанализируй тренды в следующих новостях из Telegram каналов:

{context}

Структура анализа:
1. Основные темы и события
2. Повторяющиеся сюжеты
3. Тренды и закономерности
4. Прогноз развития событий

Используй простой текст без разметки.
"""
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "meta-llama/llama-4-scout-17b-16e-instruct",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 800,
                "temperature": 0.6
            }
            
            response = requests.post(
                self.base_url,
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                trends = result['choices'][0]['message']['content'].strip()
                
                # Очищаем от проблемных символов
                trends = self.clean_markdown(trends)
                
                return f"📊 **АНАЛИЗ ТРЕНДОВ:**\n\n{trends}"
            else:
                return f"❌ Ошибка анализа трендов: {response.status_code}"
                
        except Exception as e:
            return f"❌ Ошибка при анализе трендов: {str(e)}" 