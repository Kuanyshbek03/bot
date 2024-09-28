from django import forms

from django import forms
from .models import Users_tg  # Импортируйте вашу модель User
from .models import ShortLink

class ShortLinkForm(forms.ModelForm):
    class Meta:
        model = ShortLink
        fields = ['name_of_url', 'source']
        
class MarkUserAsPaidForm(forms.ModelForm):
    class Meta:
        model = Users_tg
        fields = ['telegram_id', 'username']  # Убедитесь, что оба поля указаны здесь
        widgets = {
            'telegram_id': forms.NumberInput(attrs={'placeholder': 'Введите Telegram ID (необязательно)'}),
            'username': forms.TextInput(attrs={'placeholder': 'Введите Username (необязательно)'})
        }