from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(unique=True)
    # A short emoji/letter used on cards when there is no photo.
    glyph = models.CharField(max_length=4, default="?")
    order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Location(models.Model):
    """Named campus places. Keeping these as rows (not free text) is what
    makes location-based matching work later."""

    ZONES = [
        ("ACAD", "Academic area"),
        ("HALL", "Halls of residence"),
        ("SPORT", "Sports & Gymkhana"),
        ("SERV", "Shops, mess & services"),
        ("OPEN", "Roads & open campus"),
    ]

    name = models.CharField(max_length=80, unique=True)
    zone = models.CharField(max_length=10, choices=ZONES, default="ACAD")

    class Meta:
        ordering = ["zone", "name"]

    def __str__(self):
        return self.name


class ItemQuerySet(models.QuerySet):
    def live(self):
        return self.filter(status__in=[Item.OPEN, Item.MATCHED])

    def lost(self):
        return self.filter(kind=Item.LOST)

    def found(self):
        return self.filter(kind=Item.FOUND)

    def search(self, q):
        if not q:
            return self
        from django.db.models import Q
        terms = [t for t in q.split() if len(t) > 1]
        qs = self
        for t in terms:
            qs = qs.filter(
                Q(title__icontains=t)
                | Q(description__icontains=t)
                | Q(brand__icontains=t)
                | Q(colour__icontains=t)
                | Q(category__name__icontains=t)
                | Q(location__name__icontains=t)
                | Q(place_detail__icontains=t)
            )
        return qs.distinct()


class Item(models.Model):
    LOST, FOUND = "LOST", "FOUND"
    KINDS = [(LOST, "Lost"), (FOUND, "Found")]

    OPEN, MATCHED, CLAIMED, RETURNED, CLOSED = (
        "OPEN", "MATCHED", "CLAIMED", "RETURNED", "CLOSED",
    )
    STATUSES = [
        (OPEN, "Open"),
        (MATCHED, "Possible match"),
        (CLAIMED, "Claim in progress"),
        (RETURNED, "Returned"),
        (CLOSED, "Closed"),
    ]

    HANDOVER_CHOICES = [
        ("WITH_ME", "I'm holding it"),
        ("SECURITY", "Deposited at the Security Office"),
        ("HALL_OFFICE", "Left at the hall office"),
        ("DEPT", "Left at the department office"),
        ("IN_PLACE", "Left where I found it"),
    ]

    kind = models.CharField(max_length=6, choices=KINDS, db_index=True)
    title = models.CharField(max_length=120)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="items")
    description = models.TextField(
        help_text="Anything that would let the real owner prove it is theirs."
    )
    colour = models.CharField(max_length=40, blank=True)
    brand = models.CharField(max_length=60, blank=True)

    location = models.ForeignKey(
        Location, on_delete=models.PROTECT, related_name="items",
        help_text="Where it was lost, or where you found it.",
    )
    place_detail = models.CharField(
        max_length=140, blank=True,
        help_text="Narrow it down — 'second floor reading room', 'near the water cooler'.",
    )
    happened_on = models.DateField(default=timezone.localdate)
    happened_at = models.TimeField(null=True, blank=True)

    handover = models.CharField(max_length=20, choices=HANDOVER_CHOICES, blank=True)

    # A detail the owner must state correctly. Never shown publicly.
    secret_detail = models.CharField(
        max_length=200, blank=True,
        help_text="Only for found items. Something not visible in the photo — "
                  "a sticker, the lock screen, what's inside. Claimants must describe it.",
    )

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="items"
    )
    status = models.CharField(max_length=10, choices=STATUSES, default=OPEN, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ItemQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["kind", "status", "-created_at"]),
            models.Index(fields=["category", "kind"]),
        ]

    def __str__(self):
        return f"[{self.kind}] {self.title}"

    def get_absolute_url(self):
        return reverse("items:detail", args=[self.pk])

    @property
    def ref(self):
        """The tag number people quote to each other: LF-L-0042."""
        return f"LF-{self.kind[0]}-{self.pk:04d}"

    @property
    def cover(self):
        return self.photos.first()

    @property
    def is_open(self):
        return self.status in (self.OPEN, self.MATCHED)

    @property
    def counterpart_kind(self):
        return self.FOUND if self.kind == self.LOST else self.LOST


class ItemPhoto(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="items/%Y/%m/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]

    def __str__(self):
        return f"Photo for {self.item.ref}"


class Match(models.Model):
    """A suggested lost <-> found pairing.

    Today these come from items.matching.score_pair (plain keyword +
    location + date scoring). When the AI agent lands it writes rows into
    this same table — nothing else in the codebase has to change.
    """

    SOURCE_RULES, SOURCE_AI, SOURCE_HUMAN = "RULES", "AI", "HUMAN"
    SOURCES = [
        (SOURCE_RULES, "Rule-based"),
        (SOURCE_AI, "AI agent"),
        (SOURCE_HUMAN, "Spotted by a person"),
    ]

    lost_item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="match_as_lost")
    found_item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="match_as_found")
    score = models.FloatField(default=0)
    reasons = models.JSONField(default=list, blank=True)
    source = models.CharField(max_length=10, choices=SOURCES, default=SOURCE_RULES)
    dismissed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-score"]
        constraints = [
            models.UniqueConstraint(
                fields=["lost_item", "found_item"], name="unique_match_pair"
            )
        ]

    def __str__(self):
        return f"{self.lost_item.ref} ~ {self.found_item.ref} ({self.score:.0f}%)"


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    text = models.CharField(max_length=240)
    url = models.CharField(max_length=200, blank=True)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.text

    @classmethod
    def push(cls, user, text, url=""):
        return cls.objects.create(user=user, text=text, url=url)
