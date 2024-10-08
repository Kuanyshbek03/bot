import logging
from .utils import has_user_paid, connect_db
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import asyncio

logger = logging.getLogger(__name__)

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

async def send_scheduled_notification(bot, chat_id, content: dict) -> None:
    logger.info(f"Отправляем уведомление пользователю {chat_id}")
    
    if has_user_paid(chat_id):
        logger.info(f"Пользователь {chat_id} уже оплатил курс, уведомление не отправляется.")
        return  # Если пользователь оплатил, не отправляем уведомление
    
    content_type = content.get("type")
    text = content.get("text")
    buttons = content.get("buttons", [])

    # Создайте кнопки только если они есть
    keyboard = []
    if buttons:
        for btn in buttons:
            if "web_app" in btn:
                # Используем WebAppInfo для создания web_app кнопки
                web_app_info = WebAppInfo(url=btn["web_app"])
                keyboard.append([InlineKeyboardButton(text=btn["text"], web_app=web_app_info)])
            else:
                keyboard.append([InlineKeyboardButton(text=btn["text"], url=btn["url"])])

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None  # Установите reply_markup только если есть кнопки

    try:
        if content_type == "message":
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode='Markdown')
        elif content_type == "photo":
            photo_path = content.get("photo_path", "")
            with open(photo_path, 'rb') as photo:
                await bot.send_photo(chat_id=chat_id, photo=photo, caption=text, reply_markup=reply_markup, parse_mode='Markdown')
        logger.info(f"Отправлено {content_type} уведомление пользователю {chat_id}")
    except Exception as e:
        logger.error(f"Не удалось отправить {content_type} уведомление пользователю {chat_id}: {e}")

def get_unpaid_users():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('SELECT telegram_id FROM users WHERE telegram_id NOT IN (SELECT telegram_id FROM bot_payment WHERE is_paid = TRUE)')
    users = cursor.fetchall()
    conn.close()
    return [user[0] for user in users]

async def test_send_message(bot):
    await bot.send_message(chat_id=932249521, text="Test message")
    #asyncio.ensure_future(test_send_message(bot))

def add_notification_jobs(scheduler: AsyncIOScheduler, bot) -> None:
    unpaid_users = get_unpaid_users()  # Получаем список пользователей, которые не оплатили

    notification_schedule = [
        {
            "day": 28,
            "hour": 16,
            "minute": 57,  # Используем точное время отправки
            "content": {
                "type": "photo",
                "photo_path": r"C:\Users\Kuanysh\Загрузки\5429390754876351551.jpg",  # Путь к фото
                "text": """
*ПОСЛЕДНИЕ 3 ЧАСА* 🕒

Это твой последний шанс присоединиться к марафону!

Через 3 часа регистрация закроется, и возможности изменить себя больше не будет ❌

Не упусти этот момент — действуй сейчас и начни свой путь к лучшей версии себя вместе с AIEL 💗
""",
                "buttons": [
                    {
                        "text": "Испытать удачу 🎁",
                        "web_app": "https://40d6-2a0d-b201-40-e671-fd79-8892-a812-88d3.ngrok-free.app/wheel/"  # Замените на реальный URL WebApp
                    }
                ]
            }
        }
    ]

    for chat_id in unpaid_users:
        for schedule1 in notification_schedule:
            try:
                job_id = f"notification_{schedule1['day']}_{schedule1['hour']}_{chat_id}"
                scheduler.add_job(
                    send_scheduled_notification,
                    trigger=CronTrigger(day=schedule1["day"], hour=schedule1["hour"], minute=schedule1["minute"]),
                    args=[bot, chat_id, schedule1["content"]],
                    id=job_id,
                    replace_existing=True
                )
                logger.info(f"Задача {job_id} добавлена для пользователя {chat_id}")
            except Exception as e:
                logger.error(f"Ошибка при добавлении задачи для {chat_id}: {e}")
