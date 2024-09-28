import logging
from .utils import has_user_paid, connect_db, save_statistics
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from asgiref.sync import sync_to_async
from .models import Notification
from datetime import datetime, timezone, timedelta
from apscheduler.jobstores.base import JobLookupError
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

async def get_unpaid_users():
    conn = await sync_to_async(connect_db)()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT u.telegram_id 
        FROM users u
        LEFT JOIN bot_payment p ON u.telegram_id = p.telegram_id AND p.is_paid = TRUE
        WHERE p.telegram_id IS NULL
    ''')
    
    users = cursor.fetchall()
    conn.close()
    return [user[0] for user in users]

async def send_scheduled_notification(bot, notification: Notification) -> None:
    unpaid_users = await get_unpaid_users()

    for chat_id in unpaid_users:
        try:
            # Получаем информацию о пользователе из Telegram
            user = await bot.get_chat(chat_id)
            user_display_name = user.first_name or user.username or "Пользователь"

            # Проверяем, требуется ли включение имени пользователя
            if "{use_username}" in notification.text:
                # Подставляем имя пользователя в текст сообщения
                personalized_text = notification.text.replace("{use_username}", user_display_name)
            else:
                personalized_text = notification.text

            # Генерация short_message и unique_identifier
            short_message = (personalized_text[:50] + '...') if len(personalized_text) > 50 else personalized_text
            unique_identifier = f"{notification.id}_{notification.content_type}_{notification.day}_{notification.hour}_{notification.minute}"

            item_button = InlineKeyboardButton(text=notification.button_text or "Записаться на курс", callback_data='enroll')
            keyboard = [[item_button]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if notification.content_type == "text" and personalized_text:
                await bot.send_message(chat_id=chat_id, text=personalized_text, reply_markup=reply_markup)
            elif notification.content_type == "photo" and notification.image:
                await bot.send_photo(chat_id=chat_id, photo=notification.image.path, caption=personalized_text, reply_markup=reply_markup)
            elif notification.content_type == "video" and notification.video:
                await bot.send_video(chat_id=chat_id, video=notification.video.path, caption=personalized_text, reply_markup=reply_markup)

            save_statistics(chat_id, short_message, unique_identifier)
            logger.info(f"Отправлено {notification.content_type} уведомление пользователю {chat_id}")
        except Exception as e:
            logger.error(f"Не удалось отправить {notification.content_type} уведомление пользователю {chat_id}: {e}")

    # Обновляем статус уведомления как отправленного
    try:
        notification.sent = True
        await sync_to_async(notification.save)()
        logger.info(f"Уведомление ID {notification.id} успешно отмечено как отправленное.")
    except Exception as e:
        logger.error(f"Ошибка при обновлении статуса уведомления ID {notification.id}: {e}")


async def add_notification_jobs(scheduler: AsyncIOScheduler, bot) -> None:
    # Извлечение всех уведомлений, которые еще не были отправлены
    notifications = await sync_to_async(list)(Notification.objects.filter(sent=False))

    for notification in notifications:
        try:
            job_id = f"notification_{notification.id}"
            day = int(notification.day)
            hour = int(notification.hour)
            minute = int(notification.minute)

            now = datetime.now(timezone.utc)
            job_trigger = CronTrigger(day=day, hour=hour, minute=minute)
            
            next_fire_time = job_trigger.get_next_fire_time(None, now)
            if next_fire_time and now < next_fire_time:
                scheduler.add_job(
                    send_scheduled_notification,
                    trigger=job_trigger,
                    args=[bot, notification],
                    id=job_id,
                    replace_existing=True
                )
                logger.info(f"Задача {job_id} добавлена для отправки в {next_fire_time}")
            else:
                logger.info(f"Задача {job_id} не добавлена, так как время уже прошло.")
                # Если время прошло, задача не добавляется заново
        except Exception as e:
            logger.error(f"Ошибка при добавлении задачи {job_id}: {e}")

async def refresh_notifications(bot, scheduler):
    notifications = await sync_to_async(list)(Notification.objects.filter(sent=False))
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)

    for notification in notifications:
        job_id = f"notification_{notification.id}"
        
        day = int(notification.day)
        hour = int(notification.hour)
        minute = int(notification.minute)

        notification_time = datetime.now().replace(day=day, hour=hour, minute=minute, second=0, microsecond=0)
        notification_time = notification_time.astimezone(timezone.utc)

        if now >= notification_time:
            logger.info(f"Задача {job_id} пропущена, так как время уже прошло.")
            try:
                scheduler.remove_job(job_id)
                logger.info(f"Задача {job_id} удалена, так как время уже прошло.")
            except JobLookupError:
                logger.warning(f"Задача с ID {job_id} не найдена в планировщике.")
            continue

        try:
            scheduler.remove_job(job_id)
            logger.info(f"Задача {job_id} удалена из планировщика для обновления.")
        except JobLookupError:
            logger.warning(f"Задача с ID {job_id} не найдена в планировщике.")

        await add_notification_jobs(scheduler, bot)
        logger.info(f"Задача {job_id} добавлена заново.")

def start_scheduler(scheduler, bot):
    scheduler.add_job(
        refresh_notifications,
        trigger=IntervalTrigger(seconds=10),
        args=[bot, scheduler],
        id='refresh_notifications',
        replace_existing=True
    )
