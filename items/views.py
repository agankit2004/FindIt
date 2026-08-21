from datetime import timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from claims.models import Claim

from .forms import ItemFilterForm, ItemForm
from .matching import refresh_matches_for, suggest_for
from .models import Item, ItemPhoto, Match, Notification

MAX_PHOTOS = 4


def home(request):
    live = Item.objects.live().select_related("category", "location", "reporter")
    ctx = {
        "found_recent": live.found().prefetch_related("photos")[:8],
        "lost_recent": live.lost().prefetch_related("photos")[:8],
        "stats": {
            "lost": Item.objects.lost().count(),
            "found": Item.objects.found().count(),
            "matched": Match.objects.filter(dismissed=False).values("lost_item").distinct().count(),
            "returned": Item.objects.filter(status=Item.RETURNED).count(),
        },
        "my_open_items": Item.objects.filter(reporter=request.user).live().count(),
    }
    return render(request, "items/home.html", ctx)


def _filtered(request, kind=None):
    qs = Item.objects.live().select_related("category", "location", "reporter").prefetch_related("photos")
    if kind:
        qs = qs.filter(kind=kind)

    form = ItemFilterForm(request.GET or None)
    if form.is_valid():
        cd = form.cleaned_data
        qs = qs.search(cd.get("q"))
        if cd.get("category"):
            qs = qs.filter(category=cd["category"])
        if cd.get("location"):
            qs = qs.filter(location=cd["location"])
        if cd.get("days"):
            since = timezone.localdate() - timedelta(days=int(cd["days"]))
            qs = qs.filter(happened_on__gte=since)
    return form, qs


def item_list(request, kind=None):
    form, qs = _filtered(request, kind)
    page = Paginator(qs, 18).get_page(request.GET.get("page"))

    template = "items/_grid.html" if request.headers.get("HX-Request") else "items/list.html"
    return render(request, template, {
        "form": form,
        "page": page,
        "kind": kind,
        "heading": {"LOST": "Lost items", "FOUND": "Found items"}.get(kind, "Everything"),
        "total": qs.count(),
    })


def lost_list(request):
    return item_list(request, Item.LOST)


def found_list(request):
    return item_list(request, Item.FOUND)


def detail(request, pk):
    item = get_object_or_404(
        Item.objects.select_related("category", "location", "reporter").prefetch_related("photos"),
        pk=pk,
    )
    mine = item.reporter == request.user
    my_claim = item.claims.filter(claimant=request.user).first()

    suggestions = []
    if mine or request.user.is_staff:
        suggestions = suggest_for(item, persist=False)

    return render(request, "items/detail.html", {
        "item": item,
        "mine": mine,
        "my_claim": my_claim,
        "suggestions": suggestions,
        "claims": item.claims.select_related("claimant") if mine else None,
    })


@require_http_methods(["GET", "POST"])
def report(request, kind):
    kind = kind.upper()
    if kind not in (Item.LOST, Item.FOUND):
        return redirect("items:home")

    form = ItemForm(request.POST or None, kind=kind)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.kind = kind
        item.reporter = request.user
        item.save()

        for photo in request.FILES.getlist("photos")[:MAX_PHOTOS]:
            ItemPhoto.objects.create(item=item, image=photo)

        hits = refresh_matches_for(item)
        if hits:
            messages.success(
                request,
                f"Posted as {item.ref}. We already found {len(hits)} possible "
                f"{'match' if len(hits) == 1 else 'matches'} — check below.",
            )
        else:
            messages.success(
                request,
                f"Posted as {item.ref}. We'll alert you the moment something matches.",
            )
        return redirect(item)

    return render(request, "items/report.html", {"form": form, "kind": kind})


def my_items(request):
    items = (
        Item.objects.filter(reporter=request.user)
        .select_related("category", "location")
        .prefetch_related("photos")
        .annotate(claim_count=Count("claims"))
    )
    return render(request, "items/mine.html", {
        "open_items": [i for i in items if i.is_open],
        "closed_items": [i for i in items if not i.is_open],
    })


@require_http_methods(["POST"])
def close_item(request, pk):
    item = get_object_or_404(Item, pk=pk, reporter=request.user)
    item.status = Item.CLOSED
    item.save(update_fields=["status"])
    messages.success(request, f"{item.ref} closed. It's off the board now.")
    return redirect("items:mine")


def notifications(request):
    notes = request.user.notifications.all()[:60]
    request.user.notifications.filter(read=False).update(read=True)
    return render(request, "items/notifications.html", {"notes": notes})


def messages_hub(request):
    """Every claim thread this person is part of, newest activity first."""
    threads = (
        Claim.objects.filter(Q(claimant=request.user) | Q(item__reporter=request.user))
        .select_related("item", "claimant", "item__reporter")
        .order_by("-updated_at")
    )
    return render(request, "items/messages.html", {"threads": threads})
