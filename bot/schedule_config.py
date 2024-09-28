from utils import has_user_paid, connect_db
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Функция для отправки уведомлений в конкретные даты
async def send_scheduled_notification(bot, chat_id, text: str, button_text: str) -> None:
    # Проверяем, оплатил ли пользователь курс
    if has_user_paid(chat_id):
        return  # Если пользователь оплатил, не отправляем уведомление
    
    # Создаем кнопку с указанным текстом
    item_button = InlineKeyboardButton(text=button_text, callback_data='enroll')
    keyboard = [[item_button]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем сообщение с кнопкой
    await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup
    )

# Функция для получения всех пользователей, которые еще не оплатили
def get_unpaid_users():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('SELECT telegram_id FROM users WHERE telegram_id NOT IN (SELECT telegram_id FROM payments)')
    users = cursor.fetchall()
    conn.close()
    return [user[0] for user in users]

# Добавление задач в расписание
def add_notification_jobs(scheduler: AsyncIOScheduler, bot) -> None:
    # Получаем всех пользователей, которые еще не оплатили
    unpaid_users = get_unpaid_users()

    # Пример: Уведомление 7-го числа каждого месяца в 09:00
    for chat_id in unpaid_users:
        scheduler.add_job(
            send_scheduled_notification,
            trigger=CronTrigger(day=7, hour=9, minute=0),
            args=[bot, chat_id, "Утро доброе! Не забывайте про курс.", "Записаться на курс"],
            id=f"monthly_7th_morning_{chat_id}",
            replace_existing=True
        )

    # Пример: Уведомление 7-го числа каждого месяца в 12:00
    for chat_id in unpaid_users:
        scheduler.add_job(
            send_scheduled_notification,
            trigger=CronTrigger(day=7, hour=12, minute=0),
            args=[bot, chat_id, "Полдень! Время задуматься о своем будущем.", "Участвовать"],
            id=f"monthly_7th_noon_{chat_id}",
            replace_existing=True
        )

    # Пример: Уведомление 7-го числа каждого месяца в 18:00
    for chat_id in unpaid_users:
        scheduler.add_job(
            send_scheduled_notification,
            trigger=CronTrigger(day=7, hour=18, minute=0),
            args=[bot, chat_id, "Добрый вечер! Еще не поздно присоединиться к нашему курсу.", "Присоединиться"],
            id=f"monthly_7th_evening_{chat_id}",
            replace_existing=True
        )

    # Пример: Уведомление 15-го числа каждого месяца в 09:00
    for chat_id in unpaid_users:
        scheduler.add_job(
            send_scheduled_notification,
            trigger=CronTrigger(day=15, hour=9, minute=0),
            args=[bot, chat_id, "Напоминание! Запишитесь на курс до конца дня.", "Записаться"],
            id=f"monthly_15th_morning_{chat_id}",
            replace_existing=True
        )
    
    # Пример: Уведомление 20-го числа каждого месяца в 18:00
    for chat_id in unpaid_users:
        scheduler.add_job(
            send_scheduled_notification,
            trigger=CronTrigger(day=20, hour=18, minute=0),
            args=[bot, chat_id, "Последний шанс записаться на курс! Действуйте сейчас.", "Последний шанс"],
            id=f"monthly_20th_evening_{chat_id}",
            replace_existing=True
        )

