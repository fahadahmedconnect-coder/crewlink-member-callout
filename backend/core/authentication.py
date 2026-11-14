from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuth(SessionAuthentication):
    """Session authentication without CSRF enforcement."""
    def enforce_csrf(self, request):
        return  # Skip CSRF check
