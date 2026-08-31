import os
import requests
from datetime import timedelta
from django.utils import timezone
from django.shortcuts import redirect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from urllib.parse import urlencode
from .serializers import UserProfileSerializer

User = get_user_model()

CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
REDIRECT_URI = os.getenv("LINKEDIN_REDIRECT_URI")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


def _exchange_code_for_tokens_and_user(code):
    """
    Shared helper: exchanges code for LinkedIn tokens, fetches profile,
    creates/updates user, and returns (user, jwt_access, jwt_refresh, created, error_response)
    """
    # 1. Exchange OAuth authorization code for Access Token
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    
    token_res = requests.post(
        token_url, 
        data=payload, 
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    if token_res.status_code != 200:
        return None, None, None, False, Response({
            "error": "Failed to exchange token with LinkedIn", 
            "details": token_res.json() if token_res.content else {}
        }, status=token_res.status_code)

    token_json = token_res.json()
    access_token = token_json.get("access_token")
    refresh_token = token_json.get("refresh_token")
    expires_in = token_json.get("expires_in", 5184000)  # Default: 60 days

    # 2. Fetch User Profile using OpenID Connect endpoint
    userinfo_res = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    if userinfo_res.status_code != 200:
        return None, None, None, False, Response({"error": "Failed to retrieve user profile from LinkedIn"}, status=status.HTTP_400_BAD_REQUEST)

    profile = userinfo_res.json()
    linkedin_sub = profile.get("sub")
    email = profile.get("email")
    first_name = profile.get("given_name", "")
    last_name = profile.get("family_name", "")
    picture = profile.get("picture", "")

    if not linkedin_sub:
        return None, None, None, False, Response({"error": "LinkedIn did not return sub"}, status=status.HTTP_400_BAD_REQUEST)

    expires_at = timezone.now() + timedelta(seconds=expires_in)

    # 3. Create, fetch, or link account
    user = User.objects.filter(linkedin_sub=linkedin_sub).first()
    created = False

    if not user and email:
        # Check if user already exists by email
        user = User.objects.filter(email=email).first()

    if not user:
        # Create a brand new user
        user = User.objects.create(
            username=linkedin_sub,
            email=email,
            first_name=first_name,
            last_name=last_name,
            profile_picture=picture,
            linkedin_sub=linkedin_sub,
        )
        created = True
    else:
        # Update existing user credentials & details
        user.linkedin_sub = linkedin_sub
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        if picture:
            user.profile_picture = picture

    # 4. Save/Update OAuth credentials on user record
    user.access_token = access_token
    user.refresh_token = refresh_token
    user.token_expires_at = expires_at
    user.save()

    # 5. Issue application JWT for user session management
    jwt_refresh = RefreshToken.for_user(user)

    return user, str(jwt_refresh.access_token), str(jwt_refresh), created, None


class LinkedInAuthURLView(APIView):
    """
    Returns or redirects to the formatted LinkedIn OAuth authorization URL.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        params = {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "state": "security_state_string",  # Replace with dynamic session state in production
            "scope": "openid profile email w_member_social"
        }
        auth_url = (
            f"https://www.linkedin.com/oauth/v2/authorization?{urlencode(params)}"
        )
        return Response({"url": auth_url})


class LinkedInCallbackView(APIView):
    """
    Unified Callback View for both Account Creation (Sign Up) and Logging In.
    Handles:
    - GET: LinkedIn redirect ( ?code=xxx ) -> exchange -> redirect to frontend /auth/callback?token=...
    - POST: SPA fetch {code: xxx} -> exchange -> return JSON {tokens: {access, refresh}}
    """
    permission_classes = [AllowAny]

    def get(self, request):
        code = request.query_params.get("code")
        error = request.query_params.get("error")
        error_description = request.query_params.get("error_description")

        if error:
            # LinkedIn returned an error (user denied, etc.) - redirect to frontend with error
            params = urlencode({"error": error, "error_description": error_description or ""})
            return redirect(f"{FRONTEND_URL}/auth/callback?{params}")

        if not code:
            return redirect(f"{FRONTEND_URL}/auth/callback?error=missing_code")

        user, jwt_access, jwt_refresh, created, error_response = _exchange_code_for_tokens_and_user(code)

        if error_response:
            # Exchange failed - redirect with error
            detail = error_response.data.get("error", "token_exchange_failed")
            return redirect(f"{FRONTEND_URL}/auth/callback?error={detail}")

        # Success - redirect to frontend with tokens as query params
        # Frontend will store them in localStorage
        params = urlencode({
            "token": jwt_access,
            "refresh": jwt_refresh,
        })
        return redirect(f"{FRONTEND_URL}/auth/callback?{params}")

    def post(self, request):
        code = request.data.get("code")
        if not code:
            return Response({"error": "Authorization code is required"}, status=status.HTTP_400_BAD_REQUEST)

        user, jwt_access, jwt_refresh, created, error_response = _exchange_code_for_tokens_and_user(code)

        if error_response:
            return error_response

        return Response({
            "message": "Account created successfully" if created else "Sign in successful",
            "is_new_user": created,
            "tokens": {
                "access": jwt_access,
                "refresh": jwt_refresh,
            },
            "user": {
                "id": user.id,
                "email": user.email,
                "name": f"{user.first_name} {user.last_name}".strip(),
                "picture": user.profile_picture
            }
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class UserProfileView(APIView):
    """
    GET /api/user/profile/ - returns current authenticated user's profile
    Uses prefetch_related + select_related to fetch user and profile in 1-2 queries
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # As requested: use prefetch_related to get user and profile
        # For OneToOne, select_related is optimal for SQL JOIN, but we also use prefetch_related per spec
        user = (
            User.objects
            .prefetch_related("profile")
            .select_related("profile")
            .filter(id=request.user.id)
            .first()
        )
        if not user:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        # Fallback: ensure profile exists (signal should have created it, but handle edge)
        if not hasattr(user, "profile") or user.profile is None:
            from .models import Profile
            Profile.objects.get_or_create(user=user)
            # re-fetch with prefetch
            user = User.objects.prefetch_related("profile").select_related("profile").get(id=user.id)

        serializer = UserProfileSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        """Optional: allow updating first_name/last_name/picture"""
        from .serializers import UserUpdateSerializer
        user = User.objects.prefetch_related("profile").select_related("profile").get(id=request.user.id)
        serializer = UserUpdateSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # return full profile again
        full = UserProfileSerializer(User.objects.prefetch_related("profile").select_related("profile").get(id=user.id))
        return Response(full.data)

    def put(self, request):
        return self.patch(request)
