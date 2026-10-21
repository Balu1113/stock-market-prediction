from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


def _user_payload(user):
    return {'username': user.username, 'authenticated': True}


class RegisterView(APIView):
    def post(self, request):
        username = str(request.data.get('username', '')).strip()
        password = str(request.data.get('password', ''))
        if not username or len(username) > 150:
            return Response(
                {'error': 'Provide a username (max 150 characters).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(password) < 6:
            return Response(
                {'error': 'Password must be at least 6 characters.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if User.objects.filter(username=username).exists():
            return Response(
                {'error': 'That username is already taken.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = User.objects.create_user(username=username, password=password)
        login(request, user)
        return Response(_user_payload(user))


class LoginView(APIView):
    def post(self, request):
        username = str(request.data.get('username', '')).strip()
        password = str(request.data.get('password', ''))
        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {'error': 'Invalid username or password.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        login(request, user)
        return Response(_user_payload(user))


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response({'authenticated': False})


class MeView(APIView):
    def get(self, request):
        if request.user.is_authenticated:
            return Response(_user_payload(request.user))
        return Response({'username': '', 'authenticated': False})
