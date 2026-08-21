from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import CodeForm, EmailForm, OnboardingForm, ProfileForm
from .models import LoginCode, User, name_from_email

PENDING_KEY = "pending_email"


def _send_code(request, email):
    otp = LoginCode.issue(email)
    send_mail(
        subject=f"{otp.code} is your FindIt code",
        message=(
            f"Your FindIt sign-in code is {otp.code}\n\n"
            f"It expires in {getattr(settings, 'OTP_TTL_MINUTES', 10)} minutes. "
            "If you did not ask for this, ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )
    request.session[PENDING_KEY] = email
    return otp


@require_http_methods(["GET", "POST"])
def login_view(request):
    form = EmailForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        _send_code(request, email)
        return redirect("accounts:verify")
    return render(request, "accounts/login.html", {"form": form})


@require_http_methods(["GET", "POST"])
def verify_view(request):
    email = request.session.get(PENDING_KEY)
    if not email:
        return redirect("accounts:login")

    form = CodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        otp = LoginCode.objects.filter(email=email).first()
        if not otp:
            messages.error(request, "That code has expired. Ask for a new one.")
            return redirect("accounts:login")

        ok, error = otp.verify(form.cleaned_data["code"])
        if not ok:
            form.add_error("code", error)
        else:
            user, created = User.objects.get_or_create(
                email=email, defaults={"name": name_from_email(email)}
            )
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            request.session.pop(PENDING_KEY, None)
            # Stay signed in until they choose to sign out.
            request.session.set_expiry(settings.SESSION_COOKIE_AGE)

            if not user.profile_complete:
                return redirect("accounts:onboarding")
            nxt = request.session.pop("next_after_login", None)
            return redirect(nxt or reverse("items:home"))

    return render(request, "accounts/verify.html", {"form": form, "email": email})


def resend_view(request):
    email = request.session.get(PENDING_KEY)
    if not email:
        return redirect("accounts:login")
    _send_code(request, email)
    messages.success(request, "New code sent.")
    return redirect("accounts:verify")


@require_http_methods(["GET", "POST"])
def onboarding_view(request):
    user = request.user
    if user.profile_complete:
        return redirect("items:home")

    form = OnboardingForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.profile_complete = True
        obj.save()
        messages.success(request, "You're set. Welcome to FindIt.")
        nxt = request.session.pop("next_after_login", None)
        return redirect(nxt or reverse("items:home"))

    return render(request, "accounts/onboarding.html", {"form": form})


@require_http_methods(["GET", "POST"])
def profile_view(request):
    form = ProfileForm(
        request.POST or None, request.FILES or None, instance=request.user
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Details updated.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("accounts:login")
