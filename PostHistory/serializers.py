from rest_framework import serializers
from .models import PostHistory

class PostHistorySerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True, default=serializers.CurrentUserDefault())
    class Meta:
        model = PostHistory
        fields = ['id', 'user', 'context', 'post', 'created_at']
        extra_kwargs = {
            'user': {'read_only': True},
            'post': {'read_only': True},
        }
    def validate(self, attrs):
        if not attrs.get('context'):
            raise serializers.ValidationError("Context is required.")
        return attrs
    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user if request else None
        context_data = validated_data.get('context')
        post_data = validated_data.get('post')
        return PostHistory.objects.create(user=user, context=context_data, post=post_data)
        