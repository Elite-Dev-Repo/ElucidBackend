from django.urls import path
from .views import PostHistoryView, PostCreateView


urlpatterns = [
    path('post-history/', PostHistoryView.as_view(), name='post-history'),
    path('post-create/', PostCreateView.as_view(), name='post-create'),
]