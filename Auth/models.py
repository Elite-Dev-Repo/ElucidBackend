import os
import requests
from datetime import timedelta
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser, BaseUserManager


# Create your models here.

class CustomUserManager(BaseUserManager):
    def create_user(self, linkedin_sub, email=None, **extra_fields):
        if not linkedin_sub:
            raise ValueError("The LinkedIn Subject ID (sub) is required")
        email = self.normalize_email(email)
        user = self.model(
            username=linkedin_sub, 
            linkedin_sub=linkedin_sub, 
            email=email, 
            **extra_fields
        )
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractUser):
    # Unique OpenID Subject ID from LinkedIn
    linkedin_sub = models.CharField(max_length=255, unique=True, db_index=True)
    
    # Stored OAuth credentials for posting directly on behalf of the member
    access_token = models.TextField(blank=True, null=True)
    refresh_token = models.TextField(blank=True, null=True)
    token_expires_at = models.DateTimeField(blank=True, null=True)
    
    profile_picture = models.URLField(max_length=500, blank=True, null=True)

    USERNAME_FIELD = "linkedin_sub"
    REQUIRED_FIELDS = ["email"]

    objects = CustomUserManager()

    @property
    def is_linkedin_token_valid(self):
        if not self.access_token or not self.token_expires_at:
            return False
        return timezone.now() < self.token_expires_at

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"



class Profile(models.Model):
    PROFILE_TYPE = (
        ("free", "Free"),
        ("premium", "Premium"),
        ("supporter", "Supporter")
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    profile_type = models.CharField(max_length=20, choices=PROFILE_TYPE, default="free")
    
    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}'s Profile"