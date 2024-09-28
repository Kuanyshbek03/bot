import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    CallbackContext,
)
import asyncio
import os
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
#from schedule_config import add_notification_jobs
from .utils import generate_invoice_number, create_kaspi_order, generate_payment_link, has_user_paid, connect_db, save_statistics
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.base import JobLookupError
import logging
from datetime import datetime, timedelta
from apscheduler.triggers.date import DateTrigger
from .push_notifications import add_notification_jobs
from .bot_notifications import start_scheduler
from .statistics_utils import get_statistics
from .volna_two import start_second_wave, send_trial_lesson_callback
import os
from dotenv import load_dotenv
import time




load_dotenv()  # Загружаем переменные из .env файла

API_TOKEN = os.getenv("API_TOKEN")
MANAGER_LINK = 'https://t.me/osyraq'
# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



ALLOWED_USERS = [807477587, 932249521]
# Check if the user is allowed
def user_is_allowed(func):
    async def wrapper(update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        if user_id not in ALLOWED_USERS:
            await update.message.reply_text("You are not authorized to use this command.")
        else:
            return await func(update, context)
    return wrapper

# Получение или создание пользователя
async def get_or_create_user(telegram_id, username):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE telegram_id = %s', (telegram_id,))
    user = cursor.fetchone()
    if user is None:
        unique_number = get_next_unique_number()
        cursor.execute(
            'INSERT INTO users (telegram_id, username, unique_number) VALUES (%s, %s, %s) RETURNING *',
            (telegram_id, username, unique_number)
        )
        user = cursor.fetchone()
        conn.commit()
    conn.close()
    return user

# Получение следующего уникального номера для пользователя
def get_next_unique_number():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('SELECT MAX(unique_number) FROM users')
    max_number = cursor.fetchone()[0]
    if max_number is None:
        next_number = 100000
    else:
        next_number = max_number + 1
    conn.close()
    return next_number


def requires_no_payment(func):
    async def wrapper(update_or_chat_id, context: ContextTypes.DEFAULT_TYPE):
        user_id = None

        # Определяем ID пользователя из сообщения или callback
        if isinstance(update_or_chat_id, Update):
            if update_or_chat_id.message:
                user_id = update_or_chat_id.message.from_user.id
            elif update_or_chat_id.callback_query:
                user_id = update_or_chat_id.callback_query.from_user.id
        else:
            user_id = update_or_chat_id  # Если передан chat_id напрямую

        # Логируем ID пользователя
        logger.info(f"Проверка оплаты для пользователя с ID {user_id}")

        # Проверяем, оплатил ли пользователь
        if user_id and has_user_paid(user_id):
            # Если оплатил, блокируем действие и уведомляем
            logger.info(f"Пользователь с ID {user_id} уже оплатил курс.")
            await context.bot.send_message(chat_id=user_id, text="Вы уже оплатили курс. Доступ к этой команде закрыт.")
        else:
            # Если не оплатил, выполняем функцию
            logger.info(f"Пользователь с ID {user_id} не оплатил курс. Продолжаем выполнение команды.")
            await func(update_or_chat_id, context)

    return wrapper


# Пример сохранения задачи в базе данных
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


def restore_tasks(scheduler, bot):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, telegram_id, task_type, next_run_time FROM tasks WHERE is_completed = FALSE')
    tasks = cursor.fetchall()
    conn.close()

    for task_id, telegram_id, task_type, next_run_time in tasks:
        if next_run_time > datetime.now():
            # Задача ещё не была выполнена, планируем её на будущее
            scheduler.add_job(
                run_task,
                trigger=DateTrigger(run_date=next_run_time),
                args=[bot, task_id, telegram_id, task_type],
                id=f"task_{task_id}",
                replace_existing=True
            )
            logger.info(f"Restored task {task_type} for telegram_id {telegram_id} to run at {next_run_time}")
        else:
            # Задача должна была выполниться в прошлом, планируем её на немедленное выполнение
            scheduler.add_job(
                run_task,
                trigger=DateTrigger(run_date=datetime.now() + timedelta(seconds=5)),
                args=[bot, task_id, telegram_id, task_type],
                id=f"task_{task_id}",
                replace_existing=True
            )
            logger.info(f"Restored and rescheduled past task {task_type} for telegram_id {telegram_id} to run immediately")


async def run_task(bot, task_id, telegram_id, task_type, message_id=None):
    logger.info(f"Running task {task_type} for telegram_id {telegram_id} at {datetime.now()}")

    media_path = None
    media_type = None

    if task_type == "delete_video" and message_id:
        await delete_video(bot, telegram_id, message_id)
    elif task_type == "first_push":
        media_path = r"C:\Users\Kuanysh\Загрузки\bmw.jpeg"
        media_type = "photo"
        await send_push_notification(
            bot, 
            telegram_id, 
            "Первое уведомление через 5 минут после пробного видео. Запишитесь на курс или задайте вопрос:", 
            "Записаться на курс", 
            stage="first_push", 
            media_type=media_type, 
            media_path=media_path
        )
    elif task_type == "second_push":
        media_path = r"C:\Users\Kuanysh\Загрузки\bmw.jpeg"
        media_type = "photo"
        await send_push_notification(
            bot, 
            telegram_id, 
            "{use_username} Второе уведомление через 2 часа после первого пуша.", 
            "Участвовать", 
            stage="second_push", 
            media_type=media_type, 
            media_path=media_path
        )
    elif task_type == "third_push":
        media_path = r"C:\Users\Kuanysh\Загрузки\bmw.jpeg"
        media_type = "photo"
        await send_push_notification(
            bot, 
            telegram_id, 
            "Третье уведомление через 2 часа после второго пуша.", 
            "Присоединиться сейчас", 
            stage="third_push", 
            media_type=media_type, 
            media_path=media_path
        )
    elif task_type == "fourth_push":
        media_path = r"C:\Users\Kuanysh\Загрузки\bmw.jpeg"
        media_type = "photo"
        await send_push_notification(
            bot, 
            telegram_id, 
            "Четвертое уведомление через 2 часа после третьего пуша.", 
            "Не упустите шанс", 
            stage="fourth_push", 
            media_type=media_type, 
            media_path=media_path
        )
    elif task_type == "fifth_push":
        media_path = r"C:\Users\Kuanysh\Загрузки\bmw.jpeg"
        media_type = "photo"
        await send_push_notification(
            bot, 
            telegram_id, 
            "Пятое уведомление через 5 часов после четвертого пуша.", 
            "Последний шанс", 
            stage="fifth_push", 
            media_type=media_type, 
            media_path=media_path
        )

    # Отметить задачу как завершенную
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE tasks SET is_completed = TRUE WHERE id = %s', (task_id,))
    conn.commit()
    conn.close()
    logger.info(f"Task {task_id} for telegram_id {telegram_id} marked as completed")


async def start_push_sequence(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    if has_user_paid(chat_id):
        logger.info(f"Push notifications canceled for {chat_id} as the user already paid.")
        return
    
    scheduler = context.job_queue.scheduler

    # Сохранение и выполнение первой задачи
    start_time = datetime.now()
    next_run_time = start_time + timedelta(seconds=5)
    task_id = save_task(chat_id, "first_push", start_time, next_run_time)
    scheduler.add_job(
        run_task,
        trigger=DateTrigger(run_date=next_run_time),
        args=[context.bot, task_id, chat_id, "first_push"],
        id=f"task_{task_id}",
        replace_existing=True
    )


    # Сохранение и выполнение второй задачи
    start_time = next_run_time
    next_run_time = next_run_time + timedelta(seconds=2)
    task_id = save_task(chat_id, "second_push", start_time, next_run_time)
    scheduler.add_job(
        run_task,
        trigger=DateTrigger(run_date=next_run_time),
        args=[context.bot, task_id, chat_id, "second_push"],
        id=f"task_{task_id}",
        replace_existing=True
    )

    # И так далее для следующих пушей...
    start_time = next_run_time
    next_run_time = next_run_time + timedelta(hours =2)
    task_id = save_task(chat_id, "third_push", start_time, next_run_time)
    scheduler.add_job(
        run_task,
        trigger=DateTrigger(run_date=next_run_time),
        args=[context.bot, task_id, chat_id, "third_push"],
        id=f"task_{task_id}",
        replace_existing=True
    )

    start_time = next_run_time
    next_run_time = next_run_time + timedelta(hours=2)
    task_id = save_task(chat_id, "fourth_push", start_time, next_run_time)
    scheduler.add_job(
        run_task,
        trigger=DateTrigger(run_date=next_run_time),
        args=[context.bot, task_id, chat_id, "fourth_push"],
        id=f"task_{task_id}",
        replace_existing=True
    )

    start_time = next_run_time
    next_run_time = next_run_time + timedelta(hours=5)
    task_id = save_task(chat_id, "fifth_push", start_time, next_run_time)
    scheduler.add_job(
        run_task,
        trigger=DateTrigger(run_date=next_run_time),
        args=[context.bot, task_id, chat_id, "fifth_push"],
        id=f"task_{task_id}",
        replace_existing=True
    )

async def send_push_notification(bot, telegram_id: int, text: str, button_text: str, stage: str = None, media_type: str = None, media_path: str = None) -> None:
    if has_user_paid(telegram_id):
        logger.info(f"Skipping push notification for {telegram_id} as they have already paid.")
        return  # Не отправляем уведомление, если пользователь оплатил

    # Проверяем, требуется ли включение имени пользователя
    if "{use_username}" in text:
        # Получаем информацию о пользователе из Telegram
        user = await bot.get_chat(telegram_id)
        user_display_name = user.first_name or user.username or "Пользователь"

        # Подставляем имя пользователя в текст сообщения
        text = text.replace("{use_username}", user_display_name)
    else:
        # Убираем маркер, если он есть, но имя не нужно вставлять
        text = text.replace("{use_username}", "")

    # Генерация short_message (первые 50 символов текста)
    short_message = (text[:50] + '...') if len(text) > 50 else text

    # Генерация уникального идентификатора на основе этапа уведомления (stage)
    unique_identifier = f"{stage}" if stage else None

    # Создаем кнопку с указанным текстом
    item_bought = InlineKeyboardButton(text=button_text, callback_data='enroll')
    keyboard = [[item_bought]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        if media_type == "photo" and media_path and os.path.exists(media_path):
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


def cancel_scheduled_pushes(telegram_id):
    scheduler = AsyncIOScheduler()  # Получение текущего планировщика задач
    for task_id in ["first_push", "second_push", "third_push", "fourth_push", "fifth_push"]:
        job_id = f"task_{telegram_id}_{task_id}"
        try:
            scheduler.remove_job(job_id)
            logger.info(f"Canceled scheduled push {task_id} for {telegram_id}")
        except JobLookupError:
            logger.info(f"No scheduled push {task_id} found for {telegram_id}")

async def delete_video(bot, chat_id, message_id):
    try:
        await bot.delete_message(chat_id, message_id)
        logger.info(f"Video message {message_id} for telegram_id {chat_id} deleted.")
    except Exception as e:
        logger.error(f"Failed to delete video message {message_id} for telegram_id {chat_id}: {e}")



@requires_no_payment
async def send_video(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Начинаем отправку видео")
    
    try:
        conn = connect_db()
        cursor = conn.cursor()

        logger.info("Проверяем незавершенные задачи")
        cursor.execute('SELECT id FROM tasks WHERE telegram_id = %s AND is_completed = FALSE', (chat_id,))
        task = cursor.fetchone()

        if task is None:
            video_path = r'C:\\Users\\Kuanysh\\Загрузки\\WhatsApp Video 2024-04-18 at 00.52.04.mp4'
            if video_path and os.path.exists(video_path):
                logger.info("Видео найдено, отправляем")
                with open(video_path, 'rb') as video_file:
                    message = await context.bot.send_video(
                        chat_id,
                        video=InputFile(video_file),
                        caption="Лови свою бесплатный урок.\n⌛️(твой урок сгорит через 12 часов)",
                        protect_content=True
                    )

                    message_id = message.message_id
                    delete_time = datetime.now() + timedelta(hours=12)
                    task_id = save_task(chat_id, "delete_video", datetime.now(), delete_time)

                    context.job_queue.scheduler.add_job(
                        run_task,
                        trigger=DateTrigger(run_date=delete_time),
                        args=[context.bot, task_id, chat_id, "delete_video", message_id],
                        id=f"task_{task_id}",
                        replace_existing=True
                    )

                    cursor.execute('INSERT INTO tasks (telegram_id, task_type, start_time, next_run_time) VALUES (%s, %s, NOW(), NOW() + interval \'5 minutes\')',
                                   (chat_id, 'push_notification'))
                    conn.commit()

                    asyncio.create_task(start_push_sequence(chat_id, context))
            else:
                await context.bot.send_message(chat_id, "Видео для пробного урока не найдено. Пожалуйста, свяжитесь с поддержкой.")

        conn.close()
    
    except Exception as e:
        await context.bot.send_message(chat_id, "Произошла ошибка при отправке видео. Попробуйте позже.")
        logger.error(f"Ошибка при отправке видео: {e}")

    unique_identifier = 'free_less'
    short_message = "Отправлен пробный урок"
    save_statistics(chat_id, short_message, unique_identifier)


trial_end_date = datetime(2024, 9, 27)
    
@requires_no_payment
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await get_or_create_user(update.message.from_user.id, update.message.from_user.username)
    
    if datetime.now() > trial_end_date:
        logger.info(f"Дата {datetime.now()} превышает установленный лимит {trial_end_date}. Отправляем альтернативную цепочку сообщений.")
        await start_second_wave(update.message.chat_id, context)
        return
    # Кнопка "ХОЧУ УРОК"
    item_free = InlineKeyboardButton(text='ХОЧУ УРОК', callback_data='free_lesson')
    
    keyboard = [[item_free]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f'Привет! Это ////. Чтобы получить бесплатный урок, нажми "ХОЧУ УРОК".',
        reply_markup=reply_markup
    )
    unique_identifier = 'start_b'
    short_message = "/start - Приветственное сообщение"
    # Сохранение статистики команды /start
    save_statistics(update.message.from_user.id,short_message, unique_identifier )

# Обработчик команды /free
@requires_no_payment
async def free(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    await send_video(chat_id, context)

# Обработчик инлайн-кнопки "Пройти пробный урок"
@requires_no_payment
async def inline_free_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await send_video(query.message.chat_id, context)

# Обработчик команды /join
@requires_no_payment
async def join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id

    item_bought = InlineKeyboardButton(text='Записаться на курс', callback_data='enroll')
    reply_markup = InlineKeyboardMarkup([[item_bought]])

    await context.bot.send_message(chat_id, "Займите свое место на марафоне:", reply_markup=reply_markup)
    
    # Сохранение статистики команды /join
    unique_identifier = "join_course"
    short_message = "/join - Информация о марафоне"
    save_statistics(chat_id, short_message, unique_identifier)

# Обработчик команды /question
async def question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id

    item_question = InlineKeyboardButton(text='Задать вопрос', url=MANAGER_LINK)
    reply_markup = InlineKeyboardMarkup([[item_question]])

    await context.bot.send_message(chat_id, "Если остались вопросы, свяжитесь с нами:", reply_markup=reply_markup)
    
    # Сохранение статистики команды /question
    save_statistics(chat_id, "/question - Вопрос менеджеру")




async def enroll_course(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.callback_query.from_user.id
    query = update.callback_query
    await query.answer()

    amount = 50

    # Проверяем, если пользователь уже оплатил
    if has_user_paid(telegram_id):
        await update.callback_query.message.reply_text("Вы уже оплатили курс. Повторная оплата недоступна.")
        return

    # Проверяем, если марафон уже начался
    marathon_start_date = datetime(2024, 10, 27)
    if datetime.now() >= marathon_start_date:
        await update.callback_query.message.reply_text("Марафон уже начался. Прием оплаты закрыт.")
        return

    # Генерация уникального номера счета
    invoice_number = generate_invoice_number()

    # Удаление старых неоплаченных заказов — при необходимости можно закомментировать
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM bot_payment WHERE telegram_id = %s AND is_paid = %s', (telegram_id, False))
        conn.commit()

    # Генерация ссылок для всех методов оплаты
    kaspi_order_id = create_kaspi_order(telegram_id, amount, f"https://your_domain.com/pay/success/")
    kaspi_link = generate_payment_link(kaspi_order_id)

    # Кнопки для выбора метода оплаты
    await send_payment_options(context, query, kaspi_link)


async def send_payment_options(context, query, kaspi_link):
    robokassa_link = "https://example.com/robokassa"
    prodamus_link = "https://example.com/prodamus"

    # Кнопки для выбора метода оплаты
    keyboard = [
        [InlineKeyboardButton(text="Kaspi", url=kaspi_link)],
        [InlineKeyboardButton(text="Robokassa", url=robokassa_link)],
        [InlineKeyboardButton(text="Prodamus", url=prodamus_link)],
        [InlineKeyboardButton(text="Не могу оплатить", callback_data='cant_pay')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем новое сообщение с кнопками
    await context.bot.send_message(
        chat_id=query.from_user.id,
        text="Выберите метод оплаты:",
        reply_markup=reply_markup
    )


async def process_payment_method(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    telegram_id = query.from_user.id
    await query.answer()

    if query.data == 'cant_pay':
        keyboard = [
            [InlineKeyboardButton(text="Не могу оплатить из Казахстана", callback_data='cant_pay_kazakhstan')],
            [InlineKeyboardButton(text="Не могу оплатить другим способом", callback_data='cant_pay_other')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(text="Какой вид оплаты вызывает проблемы?", reply_markup=reply_markup)
        return
    
    elif query.data == 'cant_pay_kazakhstan':
        await send_payment_help_video(context, query, "C:\\Users\\Kuanysh\\Загрузки\\WhatsApp Video 2024-04-18 at 00.52.04.mp4")
        return

    elif query.data == 'cant_pay_other':
        await send_payment_help_video(context, query, "C:\\Users\\Kuanysh\\Загрузки\\WhatsApp Video 2024-04-18 at 00.52.04.mp4")
        return

async def send_payment_help_video(context, query, video_url):
    item_place = InlineKeyboardButton(text="Занять свое место", callback_data='enroll')
    item_support = InlineKeyboardButton(text="Остались вопросы", url=MANAGER_LINK)
    keyboard = [[item_place], [item_support]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_video(
        chat_id=query.from_user.id,
        video=video_url,
        caption="Посмотрите видеоинструкцию и выберите дальнейшее действие:",
        reply_markup=reply_markup
    )

def get_bot_instance():
    bot_instance = Application.builder().token(API_TOKEN).build().bot
    return bot_instance

async def send_payment_confirmation_admin(chat_id):
    bot = get_bot_instance()
    logging.info(f"Отправляем сообщение для {chat_id}")
    message_text = """
Поздравляю с покупкой марафона🔥🔥🔥

Ты начала новый путь с AIEL, который поможет тебе прийти к результату.

Старт марафона - 16 сентября
    """
    try:
        await bot.send_message(chat_id=chat_id, text=message_text)
    except Exception as e:
        logging.error(f"Ошибка при отправке сообщения пользователю с ID {chat_id}: {e}")

@user_is_allowed
async def stat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in ALLOWED_USERS:
        stats = await get_statistics()  # Нужно использовать await, так как get_statistics асинхронная
        await context.bot.send_message(chat_id=update.effective_chat.id, text=stats)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="У вас нет доступа к этой команде.")


# Основная функция запуска бота
def main() -> None:
    global bot_instance  # Указываем, что работаем с глобальной переменной
    print("Инициализация бота...")  # Начало функции
    
    application = Application.builder().token(API_TOKEN).build()

    print("Регистрируем обработчики команд...")
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("free", free))
    application.add_handler(CommandHandler("join", join))
    application.add_handler(CommandHandler("question", question))
    application.add_handler(CommandHandler("stat", stat_command))
    print("Регистрируем обработчики инлайн-кнопок...")
    # Регистрируем обработчики инлайн-кнопок
    application.add_handler(CallbackQueryHandler(inline_free_lesson, pattern="^free_lesson$"))
    application.add_handler(CallbackQueryHandler(send_trial_lesson_callback, pattern="^second_wave_free_video$"))
    application.add_handler(CallbackQueryHandler(enroll_course, pattern="^enroll$"))
    application.add_handler(CallbackQueryHandler(process_payment_method, pattern="^pay_"))
    # Обработчик для кнопки "Не могу оплатить"
    application.add_handler(CallbackQueryHandler(process_payment_method, pattern='^cant_pay$'))
    # Обработчики для кнопок с различными проблемами оплаты
    application.add_handler(CallbackQueryHandler(process_payment_method, pattern='^cant_pay_kazakhstan$'))
    application.add_handler(CallbackQueryHandler(process_payment_method, pattern='^cant_pay_other$'))


    print("Настраиваем планировщик...")
    # Настраиваем планировщик
    scheduler = AsyncIOScheduler()
    restore_tasks(scheduler, application.bot)
    add_notification_jobs(scheduler, application.bot)
    start_scheduler(scheduler, application.bot)
    scheduler.start()

    print("Запуск бота...")
    # Запуск бота
    application.run_polling()


if __name__ == '__main__':
    main()
