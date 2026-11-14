import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


class Local(models.Model):
    """Union local chapter (e.g., Local 27)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)  # "Local 27"
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Member(models.Model):
    """Union member (the workers who receive announcements)"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('retired', 'Retired'),
        ('suspended', 'Suspended'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    local = models.ForeignKey(Local, on_delete=models.CASCADE, related_name='members')
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    classification = models.CharField(max_length=255)  # "Journeyman Wireman", "Apprentice 3rd Year"
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['local', 'status']),
            models.Index(fields=['local', 'classification']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.classification})"


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'leadership')
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """User account for authentication (leadership or member login)"""
    ROLE_CHOICES = [
        ('member', 'Member'),
        ('leadership', 'Leadership'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    local = models.ForeignKey(Local, on_delete=models.CASCADE, null=True, blank=True, related_name='users')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    member = models.OneToOneField(Member, on_delete=models.SET_NULL, null=True, blank=True, related_name='user_account')

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return f"{self.email} ({self.role})"


class Announcement(models.Model):
    """Announcement sent to members of a local"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    local = models.ForeignKey(Local, on_delete=models.CASCADE, related_name='announcements')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_announcements')

    title = models.CharField(max_length=255)
    body = models.TextField()
    push_preview = models.CharField(max_length=120, blank=True)  # Max 120 chars for push notification

    target_classification = models.CharField(max_length=255, null=True, blank=True)  # Optional filter
    needs_ack = models.BooleanField(default=False)

    source_note = models.TextField(null=True, blank=True)  # Original messy input for AI cleanup
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_announcements')
    approved_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['local', 'status']),
            models.Index(fields=['status']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.status})"


class AnnouncementRecipient(models.Model):
    """Tracks delivery and response for each member per announcement"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name='recipients')
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='received_announcements')
    local = models.ForeignKey(Local, on_delete=models.CASCADE)  # Denormalized for fast queries

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    acked_at = models.DateTimeField(null=True, blank=True)

    # RSVP - design only, not built in Part B
    # rsvp = models.CharField(max_length=20, null=True, blank=True)  # 'coming' | 'cant'

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # Rule 2: No duplicate recipients per announcement
            models.UniqueConstraint(fields=['announcement', 'member'], name='unique_announcement_member')
        ]
        indexes = [
            models.Index(fields=['announcement', 'status']),
            models.Index(fields=['member']),
        ]

    def __str__(self):
        return f"{self.member.full_name} - {self.announcement.title} ({self.status})"
