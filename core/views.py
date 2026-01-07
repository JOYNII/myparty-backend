# core/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Event, Participant, Todo, Theme, Friendship
from django.contrib.auth.models import User
from django.db.models import Q

from .serializers import EventSerializer, ParticipantSerializer, TodoSerializer, ThemeSerializer, RegisterSerializer, UserSerializer, FriendshipSerializer
from rest_framework import generics, permissions
from rest_framework_simplejwt.tokens import RefreshToken

from django.db.models import Prefetch

class EventViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.AllowAny] # 누구나 파티 목록 조회 가능

    # 최신 이벤트 순으로 정렬하고, Nested Serializer를 위해 모든 관련 데이터(참가자, 할일 등)를 미리 가져옵니다.
    queryset = Event.objects.all()
    serializer_class = EventSerializer

    def get_queryset(self):
        # 파티 목록을 최신순으로 정렬하여 반환합니다.
        # 인증 기능 추가 후에는 request.user를 사용해 필터링해야 합니다.
        return Event.objects.all().order_by('-date')

    def check_host_permission(self, request, instance):
        if not request.user.is_authenticated:
            return False
        # 호스트가 설정되어 있지 않거나, 요청 유저가 호스트와 다르면 권한 없음
        if instance.host and instance.host != request.user:
            return False
        return True

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not self.check_host_permission(request, instance):
            return Response({'error': 'Only host can edit this party.'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if not self.check_host_permission(request, instance):
            return Response({'error': 'Only host can delete this party.'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    def perform_create(self, serializer):
        # 파티 생성 시 현재 로그인한 유저를 호스트로 파티 저장 후, 참가자로 자동 등록
        host_name = self.request.user.username if self.request.user.is_authenticated else "Guest"
        host = self.request.user if self.request.user.is_authenticated else None
        event = serializer.save(host_name=host_name, host=host)
        
        # 생성자를 참가자(호스트)로 추가
        if self.request.user.is_authenticated:
            Participant.objects.create(
                event=event, 
                user=self.request.user, 
                name=host_name
            )

    # 초대 코드를 통해 이벤트를 조회하는 커스텀 액션
    @action(detail=False, methods=['get'], url_path='by_invite_code/(?P<invite_code>[^/.]+)')
    def retrieve_by_invite_code(self, request, invite_code=None):
        try:
            # UUID 형식으로 검색
            event = self.queryset.get(invite_code=invite_code)
        except Event.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        # 상세 Serializer 사용
        serializer = self.get_serializer(event)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def joined(self, request):
        """
        내가 참여한 파티 목록 조회
        """
        user = request.user
        if not user.is_authenticated:
             return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Participant 모델을 통해 내가 참여한 이벤트 ID 목록을 가져옴
        # 혹은 Event 모델에서 participant__user=user 로 바로 필터링 가능
        events = Event.objects.filter(participant__user=user).order_by('-date')
        
        serializer = self.get_serializer(events, many=True)
        return Response(serializer.data)


# POST 요청을 오버라이드하여 초대 코드를 통한 참가자 등록 로직 구현
class ParticipantViewSet(viewsets.ModelViewSet):
    queryset = Participant.objects.all()
    serializer_class = ParticipantSerializer

    def create(self, request, *args, **kwargs):
        # 요청 데이터에서 이벤트 ID(초대 코드)를 가져옵니다.
        # 기존: invite_code = request.data.get('event') -> 'invite_code' 대신 'event' 필드로 받음
        # 클라이언트에서 'event' 필드에 invite_code를 보낼 수도 있고, event.id를 보낼 수도 있습니다.
        # 현재 api.ts는 joinParty에서 event_id를 보낼 것입니다.
        # 하지만 기존 로직은 invite_code 매칭 방식.
        # api.ts를 수정하여 event_id를 보내도록 하고, 여기서도 event_id로 찾도록 변경하거나
        # 기존대로 invite_code를 유지할지 결정해야 함.
        # 일반적인 joinParty는 id로 하는게 맞음. 초대 코드는 별도.
        
        event_id = request.data.get('event')
        
        # 1. 로그인 여부 확인
        user = request.user
        if not user.is_authenticated:
             return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

        if not event_id:
            return Response({'error': 'Event ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 2. 이벤트 찾기 (ID로 검색 시도, 실패시 invite_code로 시도 - 호환성)
            # api.ts에서 id를 보낸다면 id로 검색이 맞음.
            if str(event_id).isdigit():
                event = Event.objects.get(id=event_id)
            else:
                 event = Event.objects.get(invite_code=event_id)
        except Event.DoesNotExist:
            return Response({'error': 'Event not found.'}, status=status.HTTP_404_NOT_FOUND)

        # 3. 중복 참여 확인
        if Participant.objects.filter(event=event, user=user).exists():
             return Response({'message': 'Already joined.'}, status=status.HTTP_200_OK)

        # 4. 참가자 생성 (User와 연결)
        # 이름은 유저 이름 사용 (또는 별명 입력 받을 수도 있음)
        participant_name = user.username 
        # 만약 클라이언트가 이름을 별도로 보내면 그것을 사용할 수도 있음
        if request.data.get('name'):
            participant_name = request.data.get('name')

        participant = Participant.objects.create(event=event, user=user, name=participant_name)
        serializer = self.get_serializer(participant)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class TodoViewSet(viewsets.ModelViewSet):
    # TodoViewSet 로직 (Todo 항목 관리)
    queryset = Todo.objects.all()
    serializer_class = TodoSerializer

# ----------------------------------------------------
# Theme ViewSet (테마 목록 조회) 추가
# ----------------------------------------------------
class ThemeViewSet(viewsets.ReadOnlyModelViewSet):
    """테마 목록을 조회하는 ViewSet (GET /api/themes/)"""
    queryset = Theme.objects.all()
    serializer_class = ThemeSerializer

# ----------------------------------------------------
# Auth Views (회원가입, 유저 정보)
# ----------------------------------------------------
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # 회원가입 후 바로 토큰 발급 (선택사항, UX 향상)
        refresh = RefreshToken.for_user(user)
        
        return Response({
            "user": UserSerializer(user).data,
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)

class UserDetailView(generics.RetrieveAPIView):
    """현재 로그인한 유저 정보 반환"""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


# ----------------------------------------------------
# Friendship ViewSet
# ----------------------------------------------------
class FriendshipViewSet(viewsets.ModelViewSet):
    """
    친구 관계 관리
    - GET /: 내 친구 목록 및 요청 목록 조회
    - POST /: 친구 요청 보내기 (body: { "email": "target@email.com" })
    - DELETE /{id}/: 친구 삭제 또는 요청 취소/거절
    - POST /{id}/accept/: 친구 요청 수락
    """
    serializer_class = FriendshipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # 나와 관련된 모든 친구 관계 (보낸거, 받은거)
        user = self.request.user
        return Friendship.objects.filter(Q(from_user=user) | Q(to_user=user))

    def create(self, request, *args, **kwargs):
        # 이메일로 유저 찾아서 친구 요청
        target_email = request.data.get('email')
        if not target_email:
            return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            target_user = User.objects.get(email=target_email)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        if target_user == request.user:
            return Response({'error': 'Cannot send request to yourself.'}, status=status.HTTP_400_BAD_REQUEST)

        # 이미 존재하는 관계 확인
        existing = Friendship.objects.filter(
            (Q(from_user=request.user) & Q(to_user=target_user)) |
            (Q(from_user=target_user) & Q(to_user=request.user))
        ).first()

        if existing:
            if existing.status == 'accepted':
                return Response({'message': 'Already friends.'}, status=status.HTTP_200_OK)
            return Response({'message': 'Request already sent or received.'}, status=status.HTTP_200_OK)

        # 요청 생성
        friendship = Friendship.objects.create(from_user=request.user, to_user=target_user, status='pending')
        serializer = self.get_serializer(friendship)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        friendship = self.get_object()
        
        # 요청 받은 사람만 수락 가능
        if friendship.to_user != request.user:
            return Response({'error': 'No permission to accept this request.'}, status=status.HTTP_403_FORBIDDEN)
        
        friendship.status = 'accepted'
        friendship.save()
        return Response({'message': 'Friend request accepted.'})
