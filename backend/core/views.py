from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Q
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt

from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes, action, authentication_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuth(SessionAuthentication):
    """Session authentication without CSRF enforcement"""
    def enforce_csrf(self, request):
        return  # Skip CSRF

from .models import User, Local, Member, Announcement, AnnouncementRecipient
from .serializers import (
    UserSerializer, LoginSerializer, LocalSerializer,
    AnnouncementSerializer, AnnouncementCreateSerializer, AnnouncementListSerializer,
    AnnouncementStatsSerializer, AICleanupRequestSerializer, AICleanupResponseSerializer,
    MemberAnnouncementSerializer, MemberAnnouncementListSerializer
)
from .permissions import IsLeadership, IsMember
from ai.cleanup import cleanup_announcement_text


# ============ Auth Endpoints ============

@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuth])
@permission_classes([AllowAny])
def login_view(request):
    """POST /api/auth/login/"""
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = authenticate(
        request,
        username=serializer.validated_data['email'],
        password=serializer.validated_data['password']
    )

    if user is None:
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

    login(request, user)
    return Response(UserSerializer(user).data)


@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuth])
@permission_classes([AllowAny])
def logout_view(request):
    """POST /api/auth/logout/"""
    logout(request)
    return Response({'message': 'Logged out'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    """GET /api/auth/me/"""
    return Response(UserSerializer(request.user).data)


# ============ AI Cleanup (standalone) ============

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsLeadership])
def ai_cleanup_view(request):
    """
    POST /api/ai/cleanup/

    Standalone AI cleanup - doesn't require an announcement ID.
    Just takes messy text and returns cleaned title/body/push_preview.
    """
    serializer = AICleanupRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    result = cleanup_announcement_text(serializer.validated_data['messy_text'])

    if result is None:
        return Response(
            {'error': 'AI service unavailable, please enter manually'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    return Response(AICleanupResponseSerializer(result).data)


# ============ Base ViewSet with Local Scoping (Rule 1) ============

class LocalScopedViewSet(viewsets.ModelViewSet):
    """
    Base viewset that automatically scopes all queries to the user's local.
    This enforces Rule 1: one local's data never reaches another local.
    """
    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_superuser:
            return qs
        # Rule 1: Filter by user's local
        return qs.filter(local_id=self.request.user.local_id)


# ============ Leadership Endpoints ============

class LeadershipAnnouncementViewSet(LocalScopedViewSet):
    """
    Leadership endpoints for announcements.
    All queries automatically scoped to user's local (Rule 1).
    """
    queryset = Announcement.objects.all()
    permission_classes = [IsAuthenticated, IsLeadership]

    def get_serializer_class(self):
        if self.action == 'create':
            return AnnouncementCreateSerializer
        if self.action == 'list':
            return AnnouncementListSerializer
        return AnnouncementSerializer

    @action(detail=True, methods=['post'])
    def ai_cleanup(self, request, pk=None):
        """POST /api/leadership/announcements/{id}/ai_cleanup/"""
        announcement = self.get_object()

        if announcement.status != 'draft':
            return Response(
                {'error': 'Can only cleanup draft announcements'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = AICleanupRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Call AI cleanup (8 second timeout)
        result = cleanup_announcement_text(serializer.validated_data['messy_text'])

        if result is None:
            return Response(
                {'error': 'AI service unavailable, please enter manually'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # Update announcement with AI-generated content
        announcement.title = result['title']
        announcement.body = result['body']
        announcement.push_preview = result['push_preview'][:120]
        announcement.source_note = serializer.validated_data['messy_text']
        announcement.save()

        return Response(AICleanupResponseSerializer(result).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """POST /api/leadership/announcements/{id}/approve/"""
        announcement = self.get_object()

        if announcement.status != 'draft':
            return Response(
                {'error': 'Can only approve draft announcements'},
                status=status.HTTP_400_BAD_REQUEST
            )

        announcement.status = 'approved'
        announcement.approved_by = request.user
        announcement.approved_at = timezone.now()
        announcement.save()

        return Response(AnnouncementSerializer(announcement).data)

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        """
        POST /api/leadership/announcements/{id}/send/

        Rule 2 enforced:
        - Conditional UPDATE only succeeds once
        - ON CONFLICT DO NOTHING for recipients
        """
        announcement = self.get_object()

        with transaction.atomic():
            # Rule 2: Conditional update - only one request succeeds
            updated = Announcement.objects.filter(
                id=announcement.id,
                status='approved'
            ).update(status='sending', sent_at=timezone.now())

            if updated == 0:
                # Already sending or sent
                announcement.refresh_from_db()
                return Response(AnnouncementSerializer(announcement).data)

        # Return immediately (background worker will process recipients)
        announcement.refresh_from_db()
        return Response(
            AnnouncementSerializer(announcement).data,
            status=status.HTTP_202_ACCEPTED
        )

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """
        GET /api/leadership/announcements/{id}/stats/

        Returns counts of sent/read/acked.
        Cached for 2 seconds to prevent DB hammering.
        """
        announcement = self.get_object()
        cache_key = f'announcement_stats_{announcement.id}'

        # Check cache first
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        # Aggregate query
        stats = AnnouncementRecipient.objects.filter(
            announcement=announcement
        ).aggregate(
            total=Count('id'),
            sent=Count('id', filter=Q(status='sent')),
            read=Count('id', filter=Q(read_at__isnull=False)),
            acked=Count('id', filter=Q(acked_at__isnull=False)),
        )

        # Cache for 2 seconds
        cache.set(cache_key, stats, 2)

        return Response(stats)


# ============ Member Endpoints ============

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsMember])
def member_announcements_list(request):
    """
    GET /api/member/announcements/

    List all announcements sent to this member.
    Rule 1: Only shows announcements for member's local.
    """
    user = request.user

    if not user.member:
        return Response({'error': 'No member profile linked'}, status=status.HTTP_400_BAD_REQUEST)

    # Get all recipients for this member
    recipients = AnnouncementRecipient.objects.filter(
        member=user.member,
        status='sent'
    ).select_related('announcement').order_by('-announcement__sent_at')

    result = []
    for recipient in recipients:
        result.append({
            'id': recipient.announcement.id,
            'title': recipient.announcement.title,
            'needs_ack': recipient.announcement.needs_ack,
            'sent_at': recipient.announcement.sent_at,
            'is_read': recipient.read_at is not None,
            'is_acked': recipient.acked_at is not None,
        })

    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsMember])
def member_announcement_detail(request, pk):
    """
    GET /api/member/announcements/{id}/

    View a single announcement and auto-mark as read.
    Rule 1: Only if announcement belongs to member's local.
    """
    user = request.user

    if not user.member:
        return Response({'error': 'No member profile linked'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        recipient = AnnouncementRecipient.objects.select_related('announcement').get(
            announcement_id=pk,
            member=user.member,
            status='sent'
        )
    except AnnouncementRecipient.DoesNotExist:
        return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    # Auto-mark as read
    if recipient.read_at is None:
        recipient.read_at = timezone.now()
        recipient.save(update_fields=['read_at'])

    serializer = MemberAnnouncementSerializer(
        recipient.announcement,
        context={'recipient': recipient}
    )
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsMember])
def member_announcement_acknowledge(request, pk):
    """
    POST /api/member/announcements/{id}/acknowledge/

    Acknowledge an announcement.
    """
    user = request.user

    if not user.member:
        return Response({'error': 'No member profile linked'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        recipient = AnnouncementRecipient.objects.select_related('announcement').get(
            announcement_id=pk,
            member=user.member,
            status='sent'
        )
    except AnnouncementRecipient.DoesNotExist:
        return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    if not recipient.announcement.needs_ack:
        return Response({'error': 'This announcement does not require acknowledgment'}, status=status.HTTP_400_BAD_REQUEST)

    # Mark as acknowledged (and read if not already)
    now = timezone.now()
    if recipient.read_at is None:
        recipient.read_at = now
    if recipient.acked_at is None:
        recipient.acked_at = now
        recipient.save(update_fields=['read_at', 'acked_at'])

    return Response({'message': 'Acknowledged', 'acked_at': recipient.acked_at})
