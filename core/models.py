import uuid
from django.db import models
from django.contrib.auth.models import User


# ----------------------------------------------------
# 1. Theme 모델 (테마 선택 화면 데이터 제공)
# ----------------------------------------------------
class Theme(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return self.name


# ----------------------------------------------------
# 2. Event 모델 (장소 정보, 테마, 음식 등 필드 확장)
# ----------------------------------------------------
class Event(models.Model):
    name = models.CharField(max_length=200)
    description = models.CharField(max_length=500, blank=True, null=True) # 새로운 설명 필드
    date = models.DateField()

    #프론트엔드로부터 받을 장소 정보 필드 (4개)
    location_name = models.CharField(max_length=255, blank=True, null=True)  # 장소 이름
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)  # 위도
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)  # 경도
    place_id = models.CharField(max_length=255, blank=True, null=True)  # 구글 Place ID

    #프론트엔드로부터 받을 테마 및 음식 정보
    theme = models.CharField(max_length=50, default='기본')  # 선택된 테마 이름 저장
    food_description = models.CharField(max_length=255, blank=True, null=True)  # 음식/준비물 설명

    host_name = models.CharField(max_length=100, default='주최자') # 새로운 주최자 이름 필드
    host = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='hosted_events') # 실제 User 연결
    fee = models.IntegerField(default=0) # 새로운 참가비 필드

    # 초대 링크에 사용될 고유 코드 필드
    invite_code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    max_members = models.PositiveIntegerField(default=10)

    def __str__(self):
        return self.name


class Participant(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True) # User 모델 연결 (기존 데이터 호환 위해 null 허용)
    name = models.CharField(max_length=100)
    joined_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return self.name


class Todo(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    task = models.CharField(max_length=200)
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return self.task


# ----------------------------------------------------
# 4. ChatMessage 모델 (채팅 기록 저장)
# ----------------------------------------------------
class ChatMessage(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender.username}: {self.message[:20]}"


# ----------------------------------------------------
# 5. Friendship 모델 (친구 요청 및 관계 관리)
# ----------------------------------------------------
class Friendship(models.Model):
    from_user = models.ForeignKey(User, related_name='friendships_sent', on_delete=models.CASCADE)
    to_user = models.ForeignKey(User, related_name='friendships_received', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=10, 
        choices=[('pending', 'Pending'), ('accepted', 'Accepted')], 
        default='pending'
    )

    class Meta:
        unique_together = ('from_user', 'to_user')

    def __str__(self):
        return f"{self.from_user} -> {self.to_user} ({self.status})"
