import os
import requests
from django.db import transaction
from django.shortcuts import render
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.parsers import MultiPartParser, JSONParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PostHistory
from .serializers import PostHistorySerializer
from .services import generate_post, upload_images_to_linkedin, upload_image_to_linkedin

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
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def create(self, request, *args, **kwargs):
        user = request.user
        context_text = request.data.get('context')

        if not context_text or not str(context_text).strip():
            return Response(
                {'error': 'Context is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        context_text = str(context_text).strip()

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

        # 1c. Collect image files (supports 'images', 'image', 'file')
        image_files = []
        # getlist for each possible key
        for key in ['images', 'image', 'file', 'files']:
            if key in request.FILES:
                image_files.extend(request.FILES.getlist(key))
        # Also handle single file without getlist (rare)
        # Deduplicate by name if needed? Keep as is.

        # Validation: max 9 images (LinkedIn limit), size & type check
        if len(image_files) > 9:
            return Response(
                {'error': f'Too many images. Maximum 9 allowed, got {len(image_files)}.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        ALLOWED_TYPES = {"image/jpeg", "image/png", "image/jpg", "image/webp", "image/gif"}
        ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        for f in image_files:
            ctype = getattr(f, 'content_type', '') or ''
            # allow empty content_type if extension matches
            ext = os.path.splitext(getattr(f, 'name', '') or '')[1].lower()
            if ctype and ctype not in ALLOWED_TYPES and ext not in ALLOWED_EXTS:
                return Response(
                    {'error': f'Unsupported image type: {ctype or ext}. Allowed: jpg, jpeg, png, webp, gif'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if hasattr(f, 'size') and f.size > 10 * 1024 * 1024:
                return Response(
                    {'error': f'Image {f.name} too large ({f.size} bytes). Max 10MB.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if hasattr(f, 'size') and f.size == 0:
                return Response(
                    {'error': f'Image {f.name} is empty.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # 2. Generate post using AI service
        if use_history:
            # Serialize history to list of posts for cleaner prompt
            history_qs = PostHistory.objects.filter(user=user).values_list('post', flat=True)
            history = list(history_qs)
        else:
            history = []
        try:
            generated_post_content = generate_post(context_text, history)
        except Exception as e:
            return Response(
                {"error": "Failed to generate post", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # 2b. Upload images to LinkedIn if any (3-step flow)
        image_urns = []
        if image_files:
            try:
                image_urns = upload_images_to_linkedin(image_files, user)
            except Exception as e:
                return Response(
                    {"error": "Failed to upload image(s) to LinkedIn", "details": str(e)},
                    status=status.HTTP_502_BAD_GATEWAY
                )

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

        # Attach media if images were uploaded - per LinkedIn /rest/posts spec
        if image_urns:
            if len(image_urns) == 1:
                payload["content"] = {
                    "media": {
                        "id": image_urns[0]
                    }
                }
            else:
                # Multi-image: LinkedIn expects array of media; some versions accept media as list
                # Fallback: send as list under content.media
                payload["content"] = {
                    "media": [{"id": urn} for urn in image_urns]
                }

        try:
            linkedin_res = requests.post(url, json=payload, headers=headers, timeout=15)
        except requests.RequestException as e:
            return Response(
                {"error": "Failed to reach LinkedIn API", "details": str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        if linkedin_res.status_code != 201:
            # Try to parse error body
            try:
                details = linkedin_res.json()
            except Exception:
                details = linkedin_res.text
            return Response(
                {
                    "error": "LinkedIn failed to publish the post",
                    "details": details
                },
                status=linkedin_res.status_code
            )

        post_urn = linkedin_res.headers.get("x-restli-id", "")

        # 4. Save to PostHistory database only after successful API call
        # Store image URNs alongside if model supports it (optional field)
        create_kwargs = dict(
            user=user,
            context=context_text,
            post=generated_post_content
        )
        # If model has image_urns / image_url field, include it
        if image_urns and hasattr(PostHistory, 'image_urns'):
            create_kwargs['image_urns'] = ",".join(image_urns)

        post_history_instance = PostHistory.objects.create(**create_kwargs)

        serializer = self.get_serializer(post_history_instance)

        return Response({
            "success": True,
            "post_urn": post_urn,
            "image_urns": image_urns,
            "data": serializer.data
        }, status=status.HTTP_201_CREATED)