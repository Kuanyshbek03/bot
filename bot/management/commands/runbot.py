import logging
from django.core.management.base import BaseCommand
from bot.tg_bot import main  # Импорт функции запуска бота

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Запуск Telegram-бота'

    def handle(self, *args, **kwargs):
        try:
            self.stdout.write("Бот запущен!")
            main()
        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {e}")