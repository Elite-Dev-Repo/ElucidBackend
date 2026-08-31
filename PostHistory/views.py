import os
import requests
from django.db import transaction
from django.shortcuts import render
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PostHistory
from .serializers import PostHistorySerializer
from .services import generate_post

current_version = timezone.now().strftime("%Y%m")


class PostHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        post_history = PostHistory.objects.filter(user=request.user).order_by('-created_at')
        serializer = PostHistorySerializer(post_history, many=True)
        return Response(serializer.data)


class PostCreateView(CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PostHistorySerializer

    def create(self, request, *args, **kwargs):
        user = request.user
        context_text = request.data.get('context')

        if not context_text:
            return Response(
                {'error': 'Context is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 1. Validate LinkedIn token status
        if not getattr(user, 'is_linkedin_token_valid', False):
            return Response(
                {'error': 'LinkedIn token is expired or missing. Please log in again.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # 1b. Check use_history toggle (frontend passes use_history: true/false)
        use_history_raw = request.data.get('use_history', True)
        if isinstance(use_history_raw, bool):
            use_history = use_history_raw
        elif isinstance(use_history_raw, str):
            use_history = use_history_raw.lower() not in ('false', '0', 'no', 'off')
        elif use_history_raw is None:
            use_history = True
        else:
            use_history = bool(use_history_raw)

        # 2. Generate post using AI service
        if use_history:
            # Serialize history to list of posts for cleaner prompt
            history_qs = PostHistory.objects.filter(user=user).values_list('post', flat=True)
            history = list(history_qs)
        else:
            history = []
        generated_post_content = generate_post(context_text, history)

        # 3. Dispatch post to LinkedIn REST API
        url = os.getenv("LINKEDIN_POST_URL", "https://api.linkedin.com/rest/posts")
        headers = {
            "Authorization": f"Bearer {user.access_token}",
            "LinkedIn-Version": current_version,
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json"
        }

        payload = {
            "author": f"urn:li:person:{user.linkedin_sub}",
            "commentary": generated_post_content,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": []
            },
            "lifecycleState": "PUBLISHED"
        }

        try:
            linkedin_res = requests.post(url, json=payload, headers=headers, timeout=10)
        except requests.RequestException as e:
            return Response(
                {"error": "Failed to reach LinkedIn API", "details": str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        if linkedin_res.status_code != 201:
            return Response(
                {
                    "error": "LinkedIn failed to publish the post",
                    "details": linkedin_res.json()
                },
                status=linkedin_res.status_code
            )

        post_urn = linkedin_res.headers.get("x-restli-id", "")

        # 4. Save to PostHistory database only after successful API call
        post_history_instance = PostHistory.objects.create(
            user=user,
            context=context_text,
            post=generated_post_content
        )

        serializer = self.get_serializer(post_history_instance)

        return Response({
            "success": True,
            "post_urn": post_urn,
            "data": serializer.data
        }, status=status.HTTP_201_CREATED)