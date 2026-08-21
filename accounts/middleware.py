from django.conf import settings
from django.shortcuts import redirect
from django.urls import resolve, reverse

# URL names anyone can reach without being signed in.
PUBLIC_URL_NAMES = {
    "accounts:login",
    "accounts:verify",
    "accounts:resend",
    "accounts:logout",
}

# Path prefixes left alone entirely (Django admin has its own auth).
OPEN_PREFIXES = ("/admin/", "/static/", "/media/")


class LoginWallMiddleware:
    """Nothing on FindIt is visible until you sign in.

    Signed-in users who have not finished onboarding are held on the
    onboarding page until they do.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if path.startswith(OPEN_PREFIXES):
            return self.get_response(request)

        try:
            match = resolve(path)
            url_name = f"{match.namespace}:{match.url_name}" if match.namespace else match.url_name
        except Exception:
            url_name = None

        user = request.user

        if not user.is_authenticated:
            if url_name in PUBLIC_URL_NAMES:
                return self.get_response(request)
            request.session["next_after_login"] = request.get_full_path()
            return redirect(settings.LOGIN_URL)

        if not user.profile_complete and url_name != "accounts:onboarding":
            if url_name == "accounts:logout":
                return self.get_response(request)
            return redirect("accounts:onboarding")

        # Already signed in? The login screens are pointless.
        if url_name in {"accounts:login", "accounts:verify"} and user.profile_complete:
            return redirect(reverse("items:home"))

        return self.get_response(request)
