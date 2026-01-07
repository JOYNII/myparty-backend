# joiny_server/urls.py
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.views import EventViewSet, ParticipantViewSet, TodoViewSet, ThemeViewSet, RegisterView, UserDetailView, FriendshipViewSet
from core.serializers import EmailTokenObtainPairSerializer # Custom Serializer 임포트
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)


router = DefaultRouter()
router.register(r'events', EventViewSet, basename='event')
router.register(r'participants', ParticipantViewSet, basename='participant')
router.register(r'todos', TodoViewSet, basename='todo')
router.register(r'themes', ThemeViewSet, basename='theme') # Theme 라우팅 등록
router.register(r'friendships', FriendshipViewSet, basename='friendship')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),

    # Auth Endpoints
    path('api/auth/register/', RegisterView.as_view(), name='auth_register'),
    path('api/auth/user/', UserDetailView.as_view(), name='auth_user'),
    path('api/auth/login/', TokenObtainPairView.as_view(serializer_class=EmailTokenObtainPairSerializer), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),


    # 초대 코드를 통해 이벤트를 조회하는 새로운 엔드포인트
    path('api/events/by_invite_code/<uuid:invite_code>/', EventViewSet.as_view({'get': 'retrieve_by_invite_code'}), name='event-by-invite-code'),
]
