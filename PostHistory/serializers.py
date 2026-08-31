from rest_framework import serializers
from .models import PostHistory

class PostHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PostHistory
        fields = ['id', 'user', 'context', 'post', 'created_at']