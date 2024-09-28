from django.db import models
from django.contrib.postgres.fields import JSONField
import random
import string

class ReferralSource(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bot_referralsource'

    def __str__(self):
        return self.name

class Visit(models.Model):
    referral = models.ForeignKey(ReferralSource, on_delete=models.CASCADE)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Visit from {self.ip_address} via {self.referral.name} at {self.timestamp}"



class Notification(models.Model):
    funnel_stage = models.IntegerField()
    day = models.CharField(max_length=10)  # Можно использовать CharField для хранения значения '*'
    hour = models.CharField(max_length=10)
    minute = models.CharField(max_length=10)
    content_type = models.CharField(max_length=10, choices=[('text', 'Text'), ('photo', 'Photo'), ('video', 'Video')])
    text = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='notifications/images/', blank=True, null=True)
    video = models.FileField(upload_to='notifications/videos/', blank=True, null=True)
    button_text = models.CharField(max_length=100, blank=True, null=True)  # Новое поле для текста кнопки
    sent = models.BooleanField(default=False)  # Новое поле для отслеживания состояния отправки


    class Meta:
        db_table = 'bot_notification'

    def __str__(self):
        return f"Notification for {self.funnel_stage} at {self.hour}:{self.minute} on day {self.day}"


class Payment(models.Model):
    telegram_id = models.BigIntegerField(null=True, blank=True)  # Разрешаем null значения
    external_num = models.CharField(max_length=100)
    order_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    payment_method = models.CharField(max_length=50, null=True)

    class Meta:
        db_table = 'bot_payment'
    def __str__(self):
        return f"Payment {self.external_num} - Paid: {self.is_paid}"
    

class BotStatistics(models.Model):
    telegram_id = models.CharField(max_length=50)
    message = models.TextField()
    unique_identifier = models.CharField(max_length=100)
    delivered_at = models.DateTimeField()
    is_paid = models.BooleanField(default=False)
    purchased_after = models.BooleanField(default=False)

    class Meta:
        db_table = 'bot_statistics'  # Указываем, что модель соответствует существующей таблице

    def __str__(self):
        return f"Статистика для пользователя {self.telegram_id}"
    
class Users_tg(models.Model):
    telegram_id = models.BigIntegerField(blank=True, null=True)
    username = models.TextField(blank=True, null=True)
    unique_number = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)  # Добавляем поле для отслеживания даты создания

    class Meta:
        db_table = 'users'

    def __str__(self):
        return f"Список пользователей {self.telegram_id}"
    
def generate_short_code(length=6):
    characters = string.ascii_letters + string.digits  # Набор символов для кода
    return ''.join(random.choice(characters) for i in range(length))


class ShortLink(models.Model):
    name_of_url = models.CharField(max_length=100)  # Название ссылки
    original_url = models.CharField(max_length=500, default='https://40d6-2a0d-b201-40-e671-fd79-8892-a812-88d3.ngrok-free.app', blank=True)
    short_code = models.CharField(max_length=10, unique=True, blank=True)  # Короткий код
    source = models.CharField(max_length=100)  # Источник перехода
    click_count = models.IntegerField(default=0)  # Счетчик кликов
    url_full = models.URLField(max_length=500, blank=True)  # Поле для хранения сгенерированной полной ссылки

    class Meta:
        db_table = 'shortlink'

    def save(self, *args, **kwargs):
        # Если короткий код не указан, генерируем его
        if not self.short_code:
            self.short_code = generate_short_code()
        # Формируем полный URL
        self.url_full = f'https://40d6-2a0d-b201-40-e671-fd79-8892-a812-88d3.ngrok-free.app/{self.short_code}'
        super(ShortLink, self).save(*args, **kwargs)

    def __str__(self):
        return self.name_of_url