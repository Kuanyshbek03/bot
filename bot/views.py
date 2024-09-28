from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Payment  # Предположительно, у тебя есть модель Payment или аналогичная для хранения платежей
import psycopg2
from django.db import connection  # Для работы с базой через Django
import asyncio
import logging
from telegram import Bot
from django.shortcuts import render, redirect, get_object_or_404
from .models import ReferralSource, Visit
from django.utils import timezone
from django.http import HttpResponseRedirect
from .models import ShortLink
from django.shortcuts import redirect, get_object_or_404
from .forms import ShortLinkForm
from .utils import generate_short_code
def redirect_to_statistics(request):
    return HttpResponseRedirect('/admin/bot/botstatistics/statistics/')




def index(request):
    return render(request, 'bot/index.html')

from django.shortcuts import render, redirect
from django.http import JsonResponse
import json

def wheel_view(request):
    return render(request, 'bot/wheel.html')



# Настройка логирования
logger = logging.getLogger('myapp')  # Убедитесь, что используете правильный логгер приложения
def connect_db():
    return psycopg2.connect(
        host="localhost",
        database="Pardev",
        user="postgres",
        password="P@$$w0rd"  # Замените на ваш пароль
    )

API_TOKEN = '7339050381:AAER1DCSwq0wrXOXjbolDmeqDZ524Vqzv4o'


# Функция для обновления записи в базе, отмечая последнее сообщение как "оплачено"
def mark_as_paid(telegram_id, payment_time):
    """
    Обновляет поле is_paid для последнего сообщения пользователя до момента оплаты.
    """
    with connect_db() as conn:  # Используем правильное подключение
        cursor = conn.cursor()
  
        # Находим последнее сообщение до момента оплаты
        cursor.execute('''
            SELECT delivered_at 
            FROM bot_statistics
            WHERE telegram_id = %s AND delivered_at < %s
            ORDER BY delivered_at DESC
            LIMIT 1;
        ''', (str(telegram_id), payment_time))
        
        last_message_time = cursor.fetchone()

        if last_message_time:
            # Обновляем запись
            cursor.execute('''
                UPDATE bot_statistics
                SET is_paid = TRUE
                WHERE telegram_id = %s AND delivered_at = %s;
            ''', (str(telegram_id), last_message_time[0]))
            conn.commit()  # Коммитим изменения в базе данных

            print(f"Updated is_paid for user {telegram_id} after message at {last_message_time[0]}")
        else:
            print(f"No messages found for user {telegram_id} before payment time {payment_time}")

async def send_congratulatory_message(telegram_id):
    bot = Bot(token=API_TOKEN)
    message_text = """
Поздравляю с покупкой марафона🔥🔥🔥

Ты начала новый путь с AIEL, который поможет тебе прийти к результату.

Старт марафона - 16 сентября
    """
    try:
        await bot.send_message(chat_id=telegram_id, text=message_text)
    except Exception as e:
        logger.error(f"Failed to send message to {telegram_id}: {e}")

# Синхронная обертка для асинхронной отправки сообщений
def send_message_sync(telegram_id):
    asyncio.run(send_congratulatory_message(telegram_id))  # Используем asyncio.run для выполнения асинхронной функции

@csrf_exempt
def payment_success(request):
    if request.method == 'POST':
        order_id = request.POST.get('order_id')  # Получаем order_id от Kaspi

        try:
            # Получаем платеж по order_id
            payment = Payment.objects.get(external_num=order_id)
            
            # Обновляем статус оплаты в базе данных
            payment.is_paid = True
            payment.save()

            # Отправляем сообщение пользователю
            send_message_sync(payment.telegram_id)

            # Отмечаем в статистике, что пользователь оплатил курс
            mark_as_paid(payment.telegram_id, payment.updated_at)

            return JsonResponse({'status': 'success'}, status=200)
        except Payment.DoesNotExist:
            logger.error(f"Payment with order_id {order_id} not found")
            return JsonResponse({'status': 'error', 'message': 'Payment not found'}, status=404)
        except Exception as e:
            logger.error(f"Unexpected error for order_id {order_id}: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)



def redirect_short_link(request, short_code):
    # Ищем ссылку по короткому коду
    link = get_object_or_404(ShortLink, short_code=short_code)
    # Увеличиваем количество кликов
    link.click_count += 1
    link.save()
    # Перенаправляем на постоянный URL (сайт Telegram-бота)
    return redirect('https://t.me/Fitnes_Almaty_bot')

def create_short_link_view(request):
    if request.method == 'POST':
        form = ShortLinkForm(request.POST)
        if form.is_valid():
            short_link = form.save(commit=False)
            short_link.short_code = generate_short_code()  # Генерация короткого кода
            short_link.save()
            short_url = request.build_absolute_uri(f'/{short_link.short_code}/')
            return render(request, 'create_short_link.html', {'form': form, 'short_url': short_url})
    else:
        form = ShortLinkForm()

    return render(request, 'create_short_link.html', {'form': form})


