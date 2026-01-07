from django.contrib import admin
from .models import Theme, Event, Participant, Todo, Friendship  # 모든 모델 import

# 1. Theme 모델 등록
@admin.register(Theme)
class ThemeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')  # 관리자 목록에 보여줄 필드


# 2. 다른 모델들도 함께 등록하여 관리 편리성 높이기
@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'theme', 'invite_code')
    search_fields = ('name', 'theme')


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('name', 'event')
    list_filter = ('event',)


@admin.register(Todo)
class TodoAdmin(admin.ModelAdmin):
    list_display = ('task', 'event', 'is_completed')
    list_filter = ('event', 'is_completed')


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ('from_user', 'to_user', 'status', 'created_at')
    list_filter = ('status',)


