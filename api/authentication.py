from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Session auth without CSRF enforcement (SPA sends cookies cross-origin)."""

    def enforce_csrf(self, request):
        return
