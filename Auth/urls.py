# urls.py
from django.urls import path
from .views import LinkedInAuthURLView, LinkedInCallbackView, UserProfileView

urlpatterns = [
    path("auth/linkedin/url/", LinkedInAuthURLView.as_view(), name="linkedin_auth_url"),
    path("auth/linkedin/callback/", LinkedInCallbackView.as_view(), name="linkedin_callback"),
    path("user/profile/", UserProfileView.as_view(), name="user_profile"),
]