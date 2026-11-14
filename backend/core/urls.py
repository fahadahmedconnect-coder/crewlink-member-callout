from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'leadership/announcements', views.LeadershipAnnouncementViewSet, basename='leadership-announcements')

urlpatterns = [
    # Auth (CSRF exempt for session-based auth)
    path('auth/login/', csrf_exempt(views.login_view), name='login'),
    path('auth/logout/', csrf_exempt(views.logout_view), name='logout'),
    path('auth/me/', views.me_view, name='me'),

    # AI (standalone)
    path('ai/cleanup/', views.ai_cleanup_view, name='ai-cleanup'),

    # Leadership (ViewSet routes)
    path('', include(router.urls)),

    # Member
    path('member/announcements/', views.member_announcements_list, name='member-announcements-list'),
    path('member/announcements/<uuid:pk>/', views.member_announcement_detail, name='member-announcement-detail'),
    path('member/announcements/<uuid:pk>/acknowledge/', views.member_announcement_acknowledge, name='member-announcement-acknowledge'),
]
