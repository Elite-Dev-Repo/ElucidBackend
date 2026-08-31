from django.shortcuts import render
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import PostHistory
from .serializers import PostHistorySerializer
from rest_framework.permissions import IsAuthenticated
from .services import generate_post

# Create your views here.

class PostHistoryView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        post_history = PostHistory.objects.filter(user=request.user)
        serializer = PostHistorySerializer(post_history, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        payload_data = request.data
        if not payload_data.get('user'):
            payload_data['user'] = request.user
        if not payload_data['context']:
            return Response({'error': 'Context is required'}, status=status.HTTP_400_BAD_REQUEST)
        context = payload_data['context']
        history = PostHistory.objects.filter(user=request.user)
        post = generate_post(context, history)
        payload_data['post'] = post

        serializer = PostHistorySerializer(data=payload_data)
        if serializer.is_valid():
            PostHistory.objects.create(user = request.user, context = context, post = post)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
