from django.contrib import messages as flash
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from items.models import Item

from .forms import ClaimForm, HandoverForm, MessageForm
from .models import Claim, ClaimMessage

# What each side can do, given where the claim currently sits.
TRANSITIONS = {
    Claim.REQUESTED: {
        "holder": [
            (Claim.VERIFICATION, "Ask for more proof"),
            (Claim.APPROVED, "This is theirs — approve"),
            (Claim.REJECTED, "Doesn't match — reject"),
        ],
        "claimant": [(Claim.WITHDRAWN, "Withdraw claim")],
    },
    Claim.VERIFICATION: {
        "holder": [
            (Claim.APPROVED, "Proof checks out — approve"),
            (Claim.REJECTED, "Doesn't match — reject"),
        ],
        "claimant": [(Claim.WITHDRAWN, "Withdraw claim")],
    },
    Claim.APPROVED: {
        "holder": [(Claim.HANDOVER, "Arrange handover")],
        "claimant": [(Claim.HANDOVER, "Arrange handover"), (Claim.WITHDRAWN, "Withdraw claim")],
    },
    Claim.HANDOVER: {
        "holder": [(Claim.RETURNED, "Handed it over")],
        "claimant": [(Claim.RETURNED, "Got it back")],
    },
}


# The happy path, in order. Rejected/withdrawn are dead ends, not steps.
FLOW = [
    (Claim.REQUESTED, "Claim requested"),
    (Claim.VERIFICATION, "Being verified"),
    (Claim.APPROVED, "Approved"),
    (Claim.HANDOVER, "Arranging handover"),
    (Claim.RETURNED, "Returned"),
]


def _progress(claim):
    """Mark each step done / now / upcoming, numbered without gaps."""
    codes = [c for c, _ in FLOW]
    if claim.status in Claim.FINAL_STATUSES and claim.status != Claim.RETURNED:
        here = -1  # rejected or withdrawn: nothing after the start is live
    else:
        here = codes.index(claim.status) if claim.status in codes else 0

    steps = []
    for i, (code, label) in enumerate(FLOW):
        if here == -1:
            state = "dead" if i == 0 else ""
        elif i < here:
            state = "done"
        elif i == here:
            state = "now"
        else:
            state = ""
        steps.append({"n": i + 1, "label": label, "state": state})
    return steps


def _role(claim, user):
    if user == claim.holder:
        return "holder"
    if user == claim.claimant:
        return "claimant"
    return None


@require_http_methods(["GET", "POST"])
def create(request, item_pk):
    item = get_object_or_404(Item, pk=item_pk)

    if item.reporter == request.user:
        flash.error(request, "You posted this one.")
        return redirect(item)

    existing = item.claims.filter(claimant=request.user).first()
    if existing:
        return redirect(existing)

    # Several people may claim the same found item — the holder decides
    # between them. Only settled items are closed to new claims.
    if item.status in (Item.RETURNED, Item.CLOSED):
        flash.error(request, "This one is settled. No new claims.")
        return redirect(item)

    form = ClaimForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        claim = form.save(commit=False)
        claim.item = item
        claim.claimant = request.user
        claim.save()
        claim.advance(Claim.REQUESTED, request.user, note="Claim opened")
        flash.success(request, f"Claim {claim.ref} sent to {item.reporter.name}.")
        return redirect(claim)

    return render(request, "claims/create.html", {"form": form, "item": item})


def detail(request, pk):
    claim = get_object_or_404(
        Claim.objects.select_related("item", "claimant", "item__reporter"), pk=pk
    )
    role = _role(claim, request.user)
    if not role and not request.user.is_staff:
        flash.error(request, "That claim isn't yours.")
        return redirect("items:home")

    return render(request, "claims/detail.html", {
        "claim": claim,
        "role": role,
        "steps": _progress(claim),
        "actions": TRANSITIONS.get(claim.status, {}).get(role, []),
        "message_form": MessageForm(),
        "handover_form": HandoverForm(instance=claim),
        "thread": claim.messages.select_related("sender"),
        "events": claim.events.select_related("actor"),
    })


@require_http_methods(["POST"])
def advance(request, pk):
    claim = get_object_or_404(Claim, pk=pk)
    role = _role(claim, request.user)
    target = request.POST.get("to")

    allowed = dict(TRANSITIONS.get(claim.status, {}).get(role, []))
    if target not in allowed:
        flash.error(request, "You can't do that from here.")
        return redirect(claim)

    claim.advance(target, request.user, note=allowed[target])
    flash.success(request, f"{claim.ref} — {claim.get_status_display().lower()}.")
    return redirect(claim)


@require_http_methods(["POST"])
def post_message(request, pk):
    claim = get_object_or_404(Claim, pk=pk)
    if not _role(claim, request.user):
        return redirect("items:home")

    form = MessageForm(request.POST)
    if form.is_valid():
        msg = form.save(commit=False)
        msg.claim = claim
        msg.sender = request.user
        msg.save()
        from items.models import Notification
        Notification.push(
            claim.other_party(request.user),
            f"{request.user.name} replied about {claim.item.title}",
            claim.get_absolute_url(),
        )
    return redirect(claim)


@require_http_methods(["POST"])
def set_handover(request, pk):
    claim = get_object_or_404(Claim, pk=pk)
    if not _role(claim, request.user):
        return redirect("items:home")
    form = HandoverForm(request.POST, instance=claim)
    if form.is_valid():
        form.save()
        flash.success(request, "Handover plan saved.")
    return redirect(claim)


def my_claims(request):
    made = Claim.objects.filter(claimant=request.user).select_related("item")
    received = Claim.objects.filter(item__reporter=request.user).select_related("item", "claimant")
    return render(request, "claims/mine.html", {
        "made": made,
        "received": received,
    })
