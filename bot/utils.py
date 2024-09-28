# utils.py

import psycopg2
import requests
import time
import logging
import hashlib
from datetime import datetime
import random
import string
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from .models import ShortLink, generate_short_code
import hashlib
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()


def create_short_link(original_url, source):
    short_code = generate_short_code()  # Генерация короткого кода
    short_link = ShortLink.objects.create(
        original_url=original_url,
        short_code=short_code,
        source=source
    )
    return short_link

# Функция для генерации уникального идентификатора
def generate_unique_identifier(message_text):
    unique_string = f"{message_text}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    return hashlib.md5(unique_string.encode()).hexdigest()

def save_statistics(telegram_id, message, unique_identifier=None, is_paid=False, purchased_after=False):
    conn = connect_db()
    cursor = conn.cursor()
    
    # Получаем текущую дату и время для поля delivered_at
    delivered_at = datetime.now()

    # Вставляем данные в таблицу статистики
    cursor.execute(
        '''
        INSERT INTO bot_statistics (telegram_id, message, delivered_at, is_paid, purchased_after, unique_identifier)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''',
        (telegram_id, message, delivered_at, is_paid, purchased_after, unique_identifier)
    )
    
    conn.commit()
    conn.close()



def has_user_paid(telegram_id):
    conn = connect_db()
    cursor = conn.cursor()
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT is_paid FROM bot_payment WHERE telegram_id = %s', (telegram_id,))
        result = cursor.fetchone()

        # Логируем результат
        logger.info(f"Статус оплаты для пользователя с ID {telegram_id}: {result}")

        if result is None:
            return False  # Пользователь вообще не начинал процесс оплаты

        return result[0]  # Вернем True, если поле is_paid = True

# Функция для подключения к базе данных PostgreSQL
def connect_db():
    return psycopg2.connect(
        host="localhost",
        database="Pardev",
        user="postgres",
        password="P@$$w0rd"
    )

# Генерация уникального номера счета (external_num)
def generate_invoice_number():
    return int(time.time())


def create_or_update_payment_record(external_num, telegram_id, amount, order_id=None, payment_method=None):
    with connect_db() as conn:
        cursor = conn.cursor()

        if order_id:
            cursor.execute(
                'UPDATE bot_payment SET order_id = %s, payment_method = COALESCE(%s, payment_method), updated_at = NOW() '
                'WHERE external_num = %s AND telegram_id = %s',
                (order_id, payment_method, str(external_num), telegram_id)
            )
        else:
            cursor.execute(
                'INSERT INTO bot_payment (external_num, telegram_id, amount, is_paid, payment_method, created_at, updated_at) '
                'VALUES (%s, %s, %s, %s, %s, NOW(), NOW())',
                (str(external_num), telegram_id, amount, False, payment_method or 'Pending')
            )
        conn.commit()

    logging.info(f"Payment record for external_num {external_num} (telegram_id: {telegram_id}, payment_method: {payment_method}) updated/created.")


# Функция для обновления записи о платеже, добавляя order_id
def save_payment_order_id(external_num, order_id):
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE bot_payment SET order_id = %s, updated_at = NOW() WHERE external_num = %s',
            (order_id, str(external_num))  # Приведение external_num к строке
        )
        conn.commit()
        logging.info(f"Payment with external_num {external_num} updated with order_id {order_id}")

# Функция для отправки запроса в Kaspi и обработки ответа
def send_kaspi_request(external_num, amount, success_url):
    url = "https://aiel.fit/kaspi/addOrder"
    token = os.getenv("KASPI_TOKEN")
    
    data = {
        "external_num": external_num,
        "pay_url": success_url,
        "summa": amount,
        "token": token
    }
    
    response = requests.post(url, data=data)
    
    logging.info(f"Response status: {response.status_code}, Response text: {response.text}")
    return response

# Основная функция для создания заказа и сохранения в базе данных
def create_kaspi_order(telegram_id, amount, success_url):
    # Генерация уникального номера счета
    external_num = generate_invoice_number()

    # Создание записи в базе данных
    create_or_update_payment_record(external_num, telegram_id, amount)

    # Отправка запроса на создание заказа в Kaspi
    response = send_kaspi_request(external_num, amount, success_url)

    if response.status_code == 200:
        response_data = response.json()
        order_id = response_data.get("order_id")
        if order_id is not None:
            # Обновление записи с order_id
            save_payment_order_id(external_num, order_id)
            return order_id
        else:
            raise ValueError("Ошибка: order_id не получен")
    else:
        raise Exception(f"Ошибка при создании заказа: {response.status_code} - {response.text}")

# Функция для генерации ссылки на оплату
def generate_payment_link(order_id):
    return f"https://kaspi.kz/pay/AIELmarathon?12469={order_id}&started_from=QR"


