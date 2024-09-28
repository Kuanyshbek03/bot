from django.urls import path
from . import views
#from .admin import statistics_view  # Импортируем статистику из admin.py

urlpatterns = [
    path('', views.index, name='index'),
    path('wheel/', views.wheel_view, name='wheel'),
    #path('<slug:slug>/', views.track_visit, name='track_visit'),
    path('pay/success/', views.payment_success, name='payment_success'),
    path('<str:short_code>/', views.redirect_short_link, name='redirect_short_link'),
    path('create/', views.create_short_link_view, name='create_short_link')
    
    #path('admin/statistics_redirect/', views.redirect_to_statistics, name='statistics_redirect'),
    #path('statistics/', statistics_view, name='statistics'),
    #path('admin/statistics/', views.statistics_view, name='statistics_view'),

]