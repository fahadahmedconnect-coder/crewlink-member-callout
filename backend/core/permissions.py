from rest_framework import permissions
from functools import wraps
from rest_framework.exceptions import PermissionDenied


class IsLeadership(permissions.BasePermission):
    """Only allow leadership role"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'leadership'


class IsMember(permissions.BasePermission):
    """Only allow member role"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'member'


class IsLocalScoped(permissions.BasePermission):
    """Ensure user can only access their own local's data (Rule 1)"""
    def has_object_permission(self, request, view, obj):
        # Get local_id from the object (works for Announcement, Member, etc.)
        obj_local_id = getattr(obj, 'local_id', None)
        if obj_local_id is None and hasattr(obj, 'local'):
            obj_local_id = obj.local_id

        return obj_local_id == request.user.local_id


def require_role(role):
    """Decorator to require a specific role"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required")
            if request.user.role != role:
                raise PermissionDenied(f"Requires {role} role")
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator
