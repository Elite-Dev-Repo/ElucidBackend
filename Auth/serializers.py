from rest_framework import serializers
from .models import User, Profile


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ["profile_type"]
        read_only_fields = ["profile_type"]


class UserProfileSerializer(serializers.ModelSerializer):
    # Nested profile - read-only
    profile = ProfileSerializer(read_only=True)
    # Convenience fields
    name = serializers.SerializerMethodField()
    picture = serializers.CharField(source="profile_picture", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "name",
            "profile_picture",
            "picture",
            "linkedin_sub",
            "profile",
        ]
        read_only_fields = fields

    def get_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "profile_picture"]
