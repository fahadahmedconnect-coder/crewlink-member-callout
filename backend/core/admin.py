from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Local, Member, Announcement, AnnouncementRecipient


@admin.register(Local)
class LocalAdmin(admin.ModelAdmin):
    list_display = ['name', 'id', 'created_at']
    search_fields = ['name']


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'local', 'classification', 'status', 'email']
    list_filter = ['local', 'classification', 'status']
    search_fields = ['full_name', 'email']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'role', 'local', 'is_staff', 'is_active']
    list_filter = ['role', 'local', 'is_staff', 'is_active']
    search_fields = ['email']
    ordering = ['email']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Profile', {'fields': ('role', 'local', 'member')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'role', 'local'),
        }),
    )


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'local', 'status', 'created_by', 'sent_at', 'created_at']
    list_filter = ['local', 'status', 'needs_ack']
    search_fields = ['title', 'body']


@admin.register(AnnouncementRecipient)
class AnnouncementRecipientAdmin(admin.ModelAdmin):
    list_display = ['member', 'announcement', 'status', 'sent_at', 'read_at', 'acked_at']
    list_filter = ['status', 'announcement__local']
    search_fields = ['member__full_name']
