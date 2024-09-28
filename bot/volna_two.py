from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    CallbackContext,
)
from datetime import datetime, timedelta
from apscheduler.triggers.date import DateTrigger
import os
import logging
from .utils import connect_db, has_user_paid, save_statistics

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MANAGER_LINK = 'https://t.me/osyraq'

def save_task(telegram_id, task_type, start_time, next_run_time):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO tasks (telegram_id, task_type, start_time, next_run_time) VALUES (%s, %s, %s, %s) RETURNING id',
        (telegram_id, task_type, start_time, next_run_time)
    )
    task_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    logger.info(f"Task saved with ID {task_id} for telegram_id {telegram_id} at {next_run_time}")
    return task_id


async def start_second_wave(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Отправляем приветственное сообщение с кнопкой "Хочу видео"
    item_free = InlineKeyboardButton(text='Хочу видео', callback_data='second_wave_free_video')
    keyboard = [[item_free]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=chat_id,
        text='Привет! Это Каря, чтобы получить бесплатное видео, нажми кнопку "Хочу видео".',
        reply_markup=reply_markup
    )

async def send_trial_lesson_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id

    # Отправляем бесплатное видео
    await send_free_video(chat_id, context)

    # Запуск задачи удаления видео через 12 часов
    video_delete_time = datetime.now() + timedelta(hours=12)
    task_id = save_task(chat_id, "delete_video", datetime.now(), video_delete_time)
    context.job_queue.scheduler.add_job(
        run_task,
        trigger=DateTrigger(run_date=video_delete_time),
        args=[context.bot, task_id, chat_id, "delete_video"],
        id=f"task_{task_id}",
        replace_existing=True
    )

    # Запуск первого пуш-уведомления через 5 минут после отправки видео
    first_push_time = datetime.now() + timedelta(seconds=30)
    task_id = save_task(chat_id, "second_wave_first_push", datetime.now(), first_push_time)
    context.job_queue.scheduler.add_job(
        run_task,
        trigger=DateTrigger(run_date=first_push_time),
        args=[context.bot, task_id, chat_id, "second_wave_first_push"],
        id=f"task_{task_id}",
        replace_existing=True
    )

    # Запуск второго пуш-уведомления через 2 часа после первого пуша
    second_push_time = first_push_time + timedelta(hours=2)
    task_id = save_task(chat_id, "second_wave_second_push", datetime.now(), second_push_time)
    context.job_queue.scheduler.add_job(
        run_task,
        trigger=DateTrigger(run_date=second_push_time),
        args=[context.bot, task_id, chat_id, "second_wave_second_push"],
        id=f"task_{task_id}",
        replace_existing=True
    )

async def send_free_video(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    video_path = r'C:\\Users\\Kuanysh\\Загрузки\\WhatsApp Video 2024-04-18 at 00.52.04.mp4'
    if video_path and os.path.exists(video_path):
        with open(video_path, 'rb') as video_file:
            await context.bot.send_video(
                chat_id=chat_id,
                video=InputFile(video_file),
                caption="Лови свое бесплатное видео.\n⌛️(видео будет удалено через 12 часов)",
                protect_content=True
            )

async def run_task(bot, task_id, telegram_id, task_type, message_id=None):
    logger.info(f"Running task {task_type} for telegram_id {telegram_id} at {datetime.now()}")

    if task_type == "delete_video" and message_id:
        await delete_video(bot, telegram_id, message_id)
    elif task_type == "second_wave_first_push":
        text =   '''
Как тебе тренировка?😍

💗Мы с тобой сделали 4 МОЩНЫЕ техники:

1. Для избавления от холки
2. Для подтяжки угла молодости
3. Против сколиоза
4. От нависших век

Если выполнять эти упражнения ежедневно, то всего через 7 дней ты уже увидишь ИЗМЕНЕНИЯ! 🔥

😮‍💨 Но это только НАЧАЛО! Мы сняли ещё 36 уникальных техник для фейс пластики, осанки и многого другого

💗 Старт: 16 сентября
💗 Длительность: 3 недели + 1 бонусная неделя
💗 Цена: 4 990 тенге (вместо 14 990 тенге❌)

Нажимай на кнопку ниже и вступай в марафон прямо сейчас! 👇'''
        stage = "second_wave_first_push"
        media_path= r"C:\Users\Kuanysh\Рабочий стол\Pardev\pardev\media\notifications\images\bmw.jpeg"
        media_type="photo"
        button_text = "Занять свое место"
        await send_push_notification(bot, telegram_id, text, button_text, media_path, media_type,stage)
    elif task_type == "second_wave_second_push":
        text = '''
ТЫ ТОЖЕ УСТАЛА ОТ КРИВОЙ ОСАНКИ? 😥

Не переживай, в нашем новом марафоне мы добавили тренировки по улучшению ОСАНКИ от легендарного тренера Малики ханым! 😌

Но это еще не всё! Наш марафон — это не просто тренировки. Внутри тебя ждут:

💗 Функциональные тренировки, стретчинг, йога — всё для красоты и тонуса!
💗 Уроки от сексолога и ежедневные упражнения по интимной гимнастике для женского здоровья
💗 Персонализированное меню на каждую неделю — вкусно, сбалансировано и полезно
💗 Ежедневные медитации для полной гармонии тела и разума
💗 Личный трекер с графиком 24/7

ЗАБИРАЙ СВОЕ МЕСТО, ПОКА ОНО НЕ ДОСТАЛОСЬ ДРУГИМ! 👇'''
        stage = "second_wave_second_push"
        media_type="photo" 
        media_path = r"C:\Users\Kuanysh\Рабочий стол\Pardev\pardev\media\notifications\images\bmw.jpeg"  # Уберите запятую
        button_text = "Занять свое место"
        await send_push_notification(bot, telegram_id, text, button_text, media_path, media_type,stage)

    # Отметить задачу как завершенную
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE tasks SET is_completed = TRUE WHERE id = %s', (task_id,))
    conn.commit()
    conn.close()
    logger.info(f"Task {task_id} for telegram_id {telegram_id} marked as completed")


async def send_push_notification(bot, telegram_id: int, text: str, button_text: str, media_path: str = None, media_type: str = None, stage: str = None) -> None:
    if has_user_paid(telegram_id):
        logger.info(f"Skipping push notification for {telegram_id} as they have already paid.")
        return  # Не отправляем уведомление, если пользователь оплатил

    # Генерация короткого сообщения для сохранения статистики
    short_message = (text[:50] + '...' ) if len(text) > 50 else text

    # Генерация уникального идентификатора на основе этапа уведомления (stage)
    unique_identifier = f"{stage}" if stage else None

    # Создаем кнопку с указанным текстом
    item_bought = InlineKeyboardButton(text=button_text, callback_data='enroll')
    keyboard = [[item_bought]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        logger.info(f"Preparing to send notification to {telegram_id}. Media type: {media_type}, Media path: {media_path}")

        if media_type == "photo" and media_path and os.path.exists(media_path):
            logger.info(f"Sending photo to {telegram_id}.")
            # Отправляем фото с кнопками
            with open(media_path, 'rb') as media:
                await bot.send_photo(
                    chat_id=telegram_id,
                    photo=media,
                    caption=text,
                    reply_markup=reply_markup,
                    protect_content=True
                )
        elif media_type == "video" and media_path and os.path.exists(media_path):
            logger.info(f"Sending video to {telegram_id}.")
            # Отправляем видео с кнопками
            with open(media_path, 'rb') as media:
                await bot.send_video(
                    chat_id=telegram_id,
                    video=media,
                    caption=text,
                    reply_markup=reply_markup,
                    protect_content=True
                )
        else:
            logger.info(f"Sending text message to {telegram_id}. No media provided.")
            # Если нет ни фото, ни видео, отправляем просто текст с кнопкой
            await bot.send_message(
                chat_id=telegram_id,
                text=text,
                reply_markup=reply_markup,
                protect_content=True
            )
        logger.info(f"Push notification sent to {telegram_id} with message: {text}")

        # Сохранение статистики
        save_statistics(telegram_id, short_message, unique_identifier)

    except Exception as e:
        logger.error(f"Failed to send push notification to {telegram_id}: {e}")


async def delete_video(bot, chat_id, message_id):
    try:
        await bot.delete_message(chat_id, message_id)
        logger.info(f"Video message {message_id} for telegram_id {chat_id} deleted.")
    except Exception as e:
        logger.error(f"Failed to delete video message {message_id} for telegram_id {chat_id}: {e}")