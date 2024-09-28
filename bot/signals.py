from asgiref.sync import async_to_sync
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Users_tg, Payment
from asgiref.sync import async_to_sync
from .tg_bot import send_payment_confirmation_admin, get_bot_instance
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
'''
@receiver(post_save, sender=Payment)
def handle_payment_save(sender, instance, created, **kwargs):
    if instance.is_paid and created:
        async_to_sync(send_payment_confirmation_admin)(instance.telegram_id)'''