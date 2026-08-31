from django.urls import path
from .views import PostHistoryView


urlpatterns = [
    path('post-history/', PostHistoryView.as_view(), name='post-history'),
]