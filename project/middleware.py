import logging
from urllib.parse import quote

from django.conf import settings
from django.shortcuts import redirect


logger = logging.getLogger("project.auth")


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(request, "user", None) and request.user.is_authenticated:
            return self.get_response(request)

        path = request.path_info or "/"
        if self._is_whitelisted(path):
            return self.get_response(request)

        ip = request.META.get("REMOTE_ADDR", "")
        ua = request.META.get("HTTP_USER_AGENT", "")
        logger.warning("unauthorized_request path=%s ip=%s ua=%s", path, ip, ua)

        login_url = getattr(settings, "LOGIN_URL", "/accounts/login/")
        next_url = request.get_full_path() if request.method in {"GET", "HEAD"} else path
        return redirect(f"{login_url}?next={quote(next_url)}")

    def _is_whitelisted(self, path):
        static_url = getattr(settings, "STATIC_URL", "/static/") or "/static/"
        media_url = getattr(settings, "MEDIA_URL", "/media/") or "/media/"
        login_url = getattr(settings, "LOGIN_URL", "/accounts/login/")

        allowed_prefixes = {
            static_url,
            media_url,
            "/r/",
            "/api/r/",
        }

        allowed_exact = {
            login_url,
            "/favicon.ico",
        }

        if path in allowed_exact:
            return True
        if any(path.startswith(prefix) for prefix in allowed_prefixes):
            return True
        return False

