from .models import Item, Notification


def site_counters(request):
    """Numbers the sidebar and the stats strip need on every page."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    return {
        "unread_count": Notification.objects.filter(user=request.user, read=False).count(),
        "open_claims_count": request.user.claims_made.exclude(
            status__in=["RETURNED", "REJECTED", "WITHDRAWN"]
        ).count(),
    }
