from django.conf import settings
from django.db import models
from django.urls import reverse

from items.models import Item, Notification


class Claim(models.Model):
    """'That's mine' — the workflow from spotting an item to getting it back."""

    REQUESTED = "REQUESTED"
    VERIFICATION = "VERIFICATION"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    HANDOVER = "HANDOVER"
    RETURNED = "RETURNED"
    WITHDRAWN = "WITHDRAWN"

    STATUSES = [
        (REQUESTED, "Claim requested"),
        (VERIFICATION, "Being verified"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
        (HANDOVER, "Arranging handover"),
        (RETURNED, "Returned"),
        (WITHDRAWN, "Withdrawn"),
    ]

    OPEN_STATUSES = [REQUESTED, VERIFICATION, APPROVED, HANDOVER]
    FINAL_STATUSES = [REJECTED, RETURNED, WITHDRAWN]

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="claims")
    claimant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="claims_made"
    )
    proof = models.TextField(
        "How do you know it's yours?",
        help_text="Describe something the finder did not put in the listing.",
    )
    status = models.CharField(max_length=15, choices=STATUSES, default=REQUESTED)
    handover_plan = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["item", "claimant"], name="one_claim_per_person_per_item"
            )
        ]

    def __str__(self):
        return f"{self.claimant.name} → {self.item.ref}"

    def get_absolute_url(self):
        return reverse("claims:detail", args=[self.pk])

    @property
    def ref(self):
        return f"CL-{self.pk:04d}"

    @property
    def holder(self):
        """The person on the other side of the claim."""
        return self.item.reporter

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def contacts_unlocked(self):
        """Phone numbers appear only once the holder has approved."""
        return self.status in (self.APPROVED, self.HANDOVER, self.RETURNED)

    def other_party(self, user):
        return self.claimant if user == self.holder else self.holder

    def can_act(self, user):
        """Who is allowed to move this claim forward right now."""
        if user == self.holder:
            return self.status in (self.REQUESTED, self.VERIFICATION, self.APPROVED, self.HANDOVER)
        if user == self.claimant:
            return self.status in self.OPEN_STATUSES
        return False

    def advance(self, new_status, actor, note=""):
        old = self.status
        self.status = new_status
        self.save(update_fields=["status", "updated_at"])
        ClaimEvent.objects.create(
            claim=self, actor=actor, from_status=old, to_status=new_status, note=note
        )

        if new_status == self.RETURNED:
            self.item.status = Item.RETURNED
            self.item.save(update_fields=["status"])
        elif new_status in (self.REQUESTED, self.VERIFICATION, self.APPROVED, self.HANDOVER):
            self.item.status = Item.CLAIMED
            self.item.save(update_fields=["status"])
        elif new_status in (self.REJECTED, self.WITHDRAWN):
            if not self.item.claims.filter(status__in=self.OPEN_STATUSES).exists():
                self.item.status = Item.OPEN
                self.item.save(update_fields=["status"])

        target = self.other_party(actor)
        Notification.push(
            target,
            f"{self.item.title} — claim {self.ref} is now {self.get_status_display().lower()}",
            self.get_absolute_url(),
        )


class ClaimEvent(models.Model):
    """Append-only history. Nothing about a claim happens invisibly."""

    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    from_status = models.CharField(max_length=15)
    to_status = models.CharField(max_length=15)
    note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.claim.ref}: {self.from_status} → {self.to_status}"


class ClaimMessage(models.Model):
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.sender.name}: {self.body[:40]}"
