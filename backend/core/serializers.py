from rest_framework import serializers
from .models import User, Local, Member, Announcement, AnnouncementRecipient


class LocalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Local
        fields = ['id', 'name']


class MemberSerializer(serializers.ModelSerializer):
    """For leadership viewing member info (no contact details per Rule 1)"""
    class Meta:
        model = Member
        fields = ['id', 'full_name', 'classification', 'status']


class UserSerializer(serializers.ModelSerializer):
    local = LocalSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'role', 'local']


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


# ============ Announcement Serializers ============

class AnnouncementCreateSerializer(serializers.ModelSerializer):
    """For creating a new announcement (draft)"""
    class Meta:
        model = Announcement
        fields = ['id', 'title', 'body', 'push_preview', 'target_classification', 'needs_ack', 'source_note', 'status']
        read_only_fields = ['id', 'status']

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['local'] = user.local
        validated_data['created_by'] = user
        validated_data['status'] = 'draft'
        return super().create(validated_data)


class AnnouncementSerializer(serializers.ModelSerializer):
    """For reading announcement details"""
    created_by = UserSerializer(read_only=True)
    approved_by = UserSerializer(read_only=True)

    class Meta:
        model = Announcement
        fields = [
            'id', 'title', 'body', 'push_preview',
            'target_classification', 'needs_ack', 'source_note',
            'status', 'created_by', 'approved_by',
            'approved_at', 'sent_at', 'created_at'
        ]
        read_only_fields = ['id', 'status', 'created_by', 'approved_by', 'approved_at', 'sent_at', 'created_at']


class AnnouncementListSerializer(serializers.ModelSerializer):
    """For listing announcements (lighter)"""
    class Meta:
        model = Announcement
        fields = ['id', 'title', 'status', 'needs_ack', 'sent_at', 'created_at']


class AnnouncementStatsSerializer(serializers.Serializer):
    """For stats endpoint"""
    total = serializers.IntegerField()
    sent = serializers.IntegerField()
    read = serializers.IntegerField()
    acked = serializers.IntegerField()


# ============ AI Cleanup Serializers ============

class AICleanupRequestSerializer(serializers.Serializer):
    """Input for AI cleanup"""
    messy_text = serializers.CharField()


class AICleanupResponseSerializer(serializers.Serializer):
    """Output from AI cleanup"""
    title = serializers.CharField()
    body = serializers.CharField()
    push_preview = serializers.CharField()


# ============ Member-facing Serializers ============

class MemberAnnouncementSerializer(serializers.ModelSerializer):
    """Announcement as seen by a member"""
    is_read = serializers.SerializerMethodField()
    is_acked = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = ['id', 'title', 'body', 'needs_ack', 'sent_at', 'is_read', 'is_acked']

    def get_is_read(self, obj):
        recipient = self.context.get('recipient')
        return recipient.read_at is not None if recipient else False

    def get_is_acked(self, obj):
        recipient = self.context.get('recipient')
        return recipient.acked_at is not None if recipient else False


class MemberAnnouncementListSerializer(serializers.Serializer):
    """For listing member's announcements"""
    id = serializers.UUIDField()
    title = serializers.CharField()
    needs_ack = serializers.BooleanField()
    sent_at = serializers.DateTimeField()
    is_read = serializers.BooleanField()
    is_acked = serializers.BooleanField()
