import psycopg2
from .utils import connect_db
from .models import ShortLink, Users_tg, Payment
from django.db.models import Sum, Count
import datetime
from asgiref.sync import sync_to_async


# Функция для получения новых пользователей за день
def get_new_users_today():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at) = CURRENT_DATE")
    result = cursor.fetchone()
    conn.close()
    return result[0]

# Функция для получения оплаченных счетов и выставленных счетов
def get_invoice_statistics():
    conn = connect_db()
    cursor = conn.cursor()
    # Всего выставлено счетов
    cursor.execute("SELECT COUNT(*) FROM invoices")
    total_invoices = cursor.fetchone()[0]
    
    # Оплаченные счета
    cursor.execute("SELECT COUNT(*) FROM invoices WHERE status = 'paid'")
    paid_invoices = cursor.fetchone()[0]
    
    # Счета, оплаченные за сегодня
    cursor.execute("SELECT COUNT(*) FROM invoices WHERE status = 'paid' AND DATE(paid_at) = CURRENT_DATE")
    paid_today = cursor.fetchone()[0]

    # Общая сумма оплаченных счетов
    cursor.execute("SELECT SUM(amount) FROM invoices WHERE status = 'paid'")
    total_amount = cursor.fetchone()[0]

    conn.close()
    return total_invoices, paid_invoices, paid_today, total_amount

# Функция для получения статистики по ссылкам
def get_link_clicks():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name_of_url, click_count FROM short_links")
    result = cursor.fetchall()
    conn.close()
    return result


@sync_to_async
def get_statistics():
    today = datetime.date.today()

    # Новые пользователи за сегодня
    new_users_today = Users_tg.objects.filter(created_at__date=today).count()

    # Новые пользователи за весь период
    total_users = Users_tg.objects.all().count()

    # Счета, выставленные за сегодня
    payments_today = Payment.objects.filter(created_at__date=today).count()

    # Оплаченные счета за сегодня
    paid_today = Payment.objects.filter(
        created_at__date=today, 
        is_paid=True
    ).exclude(payment_method='Administrator').count()
    # Общая сумма оплаченных счетов за сегодня
    total_amount_today = Payment.objects.filter(
        created_at__date=today, 
        is_paid=True
    ).exclude(payment_method='Administrator').aggregate(Sum('amount'))['amount__sum'] or 0


    # Конверсия сегодня
    if payments_today > 0:
        conversion_today = (paid_today / payments_today) * 100
    else:
        conversion_today = 0

    # Общая статистика по счетам за весь период
    total_payments = Payment.objects.all().count()
    total_paid = Payment.objects.filter(is_paid=True).exclude(payment_method='Administrator').count()
    total_amount = Payment.objects.filter(is_paid=True).exclude(payment_method='Administrator').aggregate(Sum('amount'))['amount__sum'] or 0

    # Общая конверсия за весь период
    if total_payments > 0:
        total_conversion = (total_paid / total_payments) * 100
    else:
        total_conversion = 0

    # Статистика по ссылкам
    link_clicks = ShortLink.objects.all().values('name_of_url', 'short_code', 'click_count')

    # Формирование итогового текста
    stats_message = f"""
    --- Общая статистика ---
    Пользователей всего: {total_users}

    Счетов выставлено всего: {total_payments}
    Из них оплачено: {total_paid}
    На сумму: {total_amount}
    Конверсия: {total_conversion:.2f}%

    --- Статистика за сегодня ---
    Новых пользователей сегодня: {new_users_today}
    Счетов выставлено за сегодня: {payments_today}
    Оплачено сегодня: {paid_today}
    На сумму: {total_amount_today}
    Конверсия: {conversion_today:.2f}%

    --- Клики по ссылкам ---
    """
    for link in link_clicks:
        stats_message += f"{link['name_of_url']} (https://ваш_домен.com/{link['short_code']}): {link['click_count']}\n"

    return stats_message
