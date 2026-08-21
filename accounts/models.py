import random
import re
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

HALLS = [
    ("HALL1", "Hall 1"), ("HALL2", "Hall 2"), ("HALL3", "Hall 3"),
    ("HALL4", "Hall 4"), ("HALL5", "Hall 5"), ("HALL6", "Hall 6"),
    ("HALL7", "Hall 7"), ("HALL8", "Hall 8"), ("HALL9", "Hall 9"),
    ("HALL10", "Hall 10"), ("HALL11", "Hall 11"), ("HALL12", "Hall 12"),
    ("HALL13", "Hall 13"), ("GH1", "Girls Hostel 1"), ("GH2", "Girls Hostel 2"),
    ("GHT", "Girls Hostel Tower"), ("NANKARI", "Nankari"),
    ("IITK_RES", "Campus residence"), ("OFF", "Day scholar / off campus"),
]


def name_from_email(email: str) -> str:
    """Best guess at a display name from an IITK email id.

    'parvshah23@iitk.ac.in' -> 'Parvshah'
    'ankit.agarwal21@iitk.ac.in' -> 'Ankit Agarwal'
    'aagarwal@iitk.ac.in' -> 'Aagarwal'

    IITK ids are not consistently structured, so this is only a starting
    point. The user confirms or corrects it once during onboarding, and
    after that the name is locked.
    """
    local = email.split("@")[0]
    local = re.sub(r"\d+", "", local)
    parts = [p for p in re.split(r"[._\-]+", local) if p]
    return " ".join(p.capitalize() for p in parts) or local.capitalize()


class UserManager(BaseUserManager):
    def create_user(self, email, **extra):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        extra.setdefault("name", name_from_email(email))
        user = self.model(email=email, **extra)
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("profile_complete", True)
        email = self.normalize_email(email).lower()
        extra.setdefault("name", name_from_email(email))
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    # Locked after onboarding. Staff can still correct it from the admin.
    name = models.CharField(max_length=120)
    hall = models.CharField(max_length=20, choices=HALLS, blank=True)
    room = models.CharField("Room number", max_length=20, blank=True)
    phone = models.CharField("Contact number", max_length=15, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    profile_complete = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} <{self.email}>"

    @property
    def roll_id(self):
        return self.email.split("@")[0]

    @property
    def initials(self):
        bits = self.name.split()
        return ("".join(b[0] for b in bits[:2]) or self.email[0]).upper()

    @property
    def where(self):
        if self.room and self.hall:
            return f"{self.get_hall_display()}, Room {self.room}"
        return self.get_hall_display() or "—"


class LoginCode(models.Model):
    """A single-use 6-digit code emailed to a campus address."""

    MAX_ATTEMPTS = 5

    email = models.EmailField(db_index=True)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email} · {self.code}"

    @classmethod
    def issue(cls, email):
        email = email.lower().strip()
        cls.objects.filter(email=email, used_at__isnull=True).delete()
        ttl = getattr(settings, "OTP_TTL_MINUTES", 10)
        return cls.objects.create(
            email=email,
            code=f"{random.randint(0, 999999):06d}",
            expires_at=timezone.now() + timedelta(minutes=ttl),
        )

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def seconds_left(self):
        return max(0, int((self.expires_at - timezone.now()).total_seconds()))

    def verify(self, submitted):
        """Returns (ok, error_message)."""
        if self.used_at:
            return False, "That code has already been used. Ask for a new one."
        if self.is_expired:
            return False, "That code has expired. Ask for a new one."
        if self.attempts >= self.MAX_ATTEMPTS:
            return False, "Too many wrong attempts. Ask for a new code."
        if submitted.strip() != self.code:
            self.attempts += 1
            self.save(update_fields=["attempts"])
            left = self.MAX_ATTEMPTS - self.attempts
            return False, f"That code is not right. {left} attempts left."
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])
        return True, ""
