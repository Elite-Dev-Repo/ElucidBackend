from django.db import models
from django.contrib.auth import get_user_model

# Create your models here.

User = get_user_model()

class PostHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    context = models.CharField(max_length=255)
    post = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"PostHistory: {self.user}"
