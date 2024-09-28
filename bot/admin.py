from django.contrib import admin, messages
from django.template.response import TemplateResponse
from django.db.models import Count, Q
from django.urls import reverse, path
from .models import BotStatistics, Notification, Users_tg, Payment   # Убедитесь, что импортируется правильная модель User
from .forms import MarkUserAsPaidForm, ShortLinkForm
from telegram import Bot
from django.utils import timezone
from django.utils.html import format_html
from .tg_bot import send_payment_confirmation_admin
from asgiref.sync import async_to_sync
from .models import ShortLink
from .utils import generate_short_code

# Telegram Bot Token

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('funnel_stage', 'day', 'hour', 'minute', 'content_type', 'sent')
    fields = ('funnel_stage', 'day', 'hour', 'minute', 'content_type', 'text', 'image', 'video', 'button_text', 'sent')

@admin.register(ShortLink)
class ShortLinkAdmin(admin.ModelAdmin):
    list_display = ('name_of_url', 'source', 'short_code', 'click_count', 'get_short_link')

    def save_model(self, request, obj, form, change):
        if not obj.short_code:
            obj.short_code = generate_short_code()
        obj.save()

    def get_short_link(self, obj):
        domain = 'https://40d6-2a0d-b201-40-e671-fd79-8892-a812-88d3.ngrok-free.app'
        return format_html('<a href="{}/{}/" target="_blank">{}/{}</a>', domain, obj.short_code, domain, obj.short_code)
    
    get_short_link.short_description = 'Short link'

class BotStatisticsAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'message', 'delivered_at', 'is_paid', 'purchased_after')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('statistics/', self.admin_site.admin_view(self.statistics_view), name='statistics'),
        ]
        return custom_urls + urls
    
    def statistics_view(self, request):
        total_users = BotStatistics.objects.values('telegram_id').distinct().count()
        total_purchases = BotStatistics.objects.filter(is_paid=True).values('telegram_id').distinct().count()

        stats = BotStatistics.objects.values('message', 'unique_identifier').annotate(
            total_messages=Count('telegram_id', distinct=True),
            total_purchases=Count('telegram_id', filter=Q(is_paid=True), distinct=True)
        )

        for stat in stats:
            if stat['total_messages'] > 0:
                stat['conversion_rate'] = (stat['total_purchases'] / stat['total_messages']) * 100
            else:
                stat['conversion_rate'] = 0

        # Добавляем общую статистику в начало списка
        stats = list(stats)
        stats.insert(0, {
            'unique_identifier': 'Общая статистика',
            'message': '',
            'total_messages': total_users,
            'total_purchases': total_purchases,
            'conversion_rate': (total_purchases / total_users) * 100 if total_users > 0 else 0
        })
        context = dict(
            self.admin_site.each_context(request),
            stats=stats
        )
        return TemplateResponse(request, "admin/statistics.html", context)
    
class MarkUserAsPaidAdmin(admin.ModelAdmin):
    form = MarkUserAsPaidForm
    change_list_template = "admin/mark_user_as_paid.html"

class MarkUserAsPaidAdmin(admin.ModelAdmin):
    form = MarkUserAsPaidForm
    change_list_template = "admin/mark_user_as_paid.html"

    def changelist_view(self, request, extra_context=None):
        if request.method == 'POST':
            form = self.get_form(request.POST)
            form_instance = form(request.POST)
            if form_instance.is_valid():
                username = form_instance.cleaned_data['username']
                telegram_id = form_instance.cleaned_data['telegram_id']

                user = None

                # Ищем пользователя по username, если он указан
                if username:
                    user = Users_tg.objects.filter(username=username).first()
                    if user:
                        telegram_id = user.telegram_id  # Получаем telegram_id пользователя, если он найден

                # Если указан telegram_id, и пользователя не нашли по username, ищем по telegram_id
                if telegram_id and not user:
                    user = Users_tg.objects.filter(telegram_id=telegram_id).first()

                if user:
                    # Проверяем, существует ли запись о платеже
                    payment = Payment.objects.filter(telegram_id=telegram_id).first()
                    if payment:
                        if not payment.is_paid:
                            # Если запись существует и не оплачена, обновляем её
                            payment.amount = 0.00
                            payment.is_paid = True
                            payment.payment_method = 'Administrator'
                            payment.updated_at = timezone.now()
                            payment.save()
                            messages.success(request, f"Пользователь {username or telegram_id} найден, и оплата отмечена.")
                        else:
                            messages.info(request, "Оплата уже была отмечена ранее.")
                    else:
                        # Если записи о платеже нет, создаем новую
                        Payment.objects.create(
                            telegram_id=telegram_id,
                            external_num="AdminPayment",  # Можно заменить на уникальный номер
                            amount=0.00,  # Если нужно, можно указать сумму платежа
                            is_paid=True,
                            payment_method='Administrator',
                            created_at=timezone.now(),
                            updated_at=timezone.now()
                        )
                        messages.success(request, f"Пользователь {username or telegram_id} найден, и новая оплата была создана.")

                    # Отправляем сообщение пользователю после успешной оплаты
                    async_to_sync(send_payment_confirmation_admin)(telegram_id)
                else:
                    # Если пользователь не найден, выводим сообщение с ссылкой на бот
                    bot_link = format_html('<a href="https://t.me/Fitnes_Almaty_bot" target="_blank">Нажмите старт у бота</a>')
                    messages.error(request, format_html(f"Такого человека в базе нету. {bot_link}."))
            else:
                messages.error(request, "Ошибка в форме. Проверьте данные.")

        extra_context = extra_context or {}
        extra_context['form'] = MarkUserAsPaidForm()

        return super(MarkUserAsPaidAdmin, self).changelist_view(request, extra_context=extra_context)

class CustomAdminSite(admin.AdminSite):
    site_header = "Управление ботом"
    site_title = "Панель администратора"
    index_title = "Добро пожаловать в панель администратора"

    def each_context(self, request):
        context = super().each_context(request)
        context['statistics_link'] = reverse('admin:statistics')
        return context

admin_site = CustomAdminSite(name='custom_admin')
admin.site.register(BotStatistics, BotStatisticsAdmin)
admin.site.register(Users_tg, MarkUserAsPaidAdmin)
