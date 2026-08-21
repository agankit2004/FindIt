"""Candidate matching.

This is the seam the AI agent slots into later. Everything else in the
project calls `suggest_for(item)` and does not care how the scores were
produced. To go agentic, keep this signature and change the inside:
embed the descriptions, compare vectors, let an LLM read the top few and
write the `reasons` list.
"""

from datetime import timedelta

from .models import Item, Match

STOPWORDS = {
    "a", "an", "the", "my", "i", "it", "is", "was", "in", "on", "at", "near",
    "of", "and", "with", "lost", "found", "some", "somewhere", "around",
    "black", "white",  # too common to be informative on their own
}

# How much each signal is worth. Tune these against real data.
W_CATEGORY = 35
W_LOCATION = 20
W_ZONE = 8
W_DATE = 15
W_COLOUR = 12
W_BRAND = 15
W_WORDS = 20


def _tokens(item):
    raw = f"{item.title} {item.description} {item.brand} {item.place_detail}".lower()
    keep = []
    for word in raw.replace(",", " ").replace(".", " ").split():
        word = word.strip("()[]'\"-/")
        if len(word) > 2 and word not in STOPWORDS:
            keep.append(word)
    return set(keep)


def score_pair(lost, found):
    """Return (score 0-100, list of human-readable reasons)."""
    score, reasons = 0.0, []

    if lost.category_id == found.category_id:
        score += W_CATEGORY
        reasons.append(f"Both are {lost.category.name.lower()}")

    if lost.location_id == found.location_id:
        score += W_LOCATION
        reasons.append(f"Same place — {lost.location.name}")
    elif lost.location.zone == found.location.zone:
        score += W_ZONE
        reasons.append(f"Both in the {lost.location.get_zone_display().lower()}")

    gap = abs((found.happened_on - lost.happened_on).days)
    if gap == 0:
        score += W_DATE
        reasons.append("Same day")
    elif gap <= 2:
        score += W_DATE * 0.7
        reasons.append(f"{gap} day{'s' if gap > 1 else ''} apart")
    elif gap <= 7:
        score += W_DATE * 0.3
        reasons.append("Same week")

    if lost.colour and found.colour and lost.colour.lower() == found.colour.lower():
        score += W_COLOUR
        reasons.append(f"Both {lost.colour.lower()}")

    if lost.brand and found.brand and lost.brand.lower() == found.brand.lower():
        score += W_BRAND
        reasons.append(f"Both {lost.brand}")

    shared = _tokens(lost) & _tokens(found)
    if shared:
        score += min(W_WORDS, len(shared) * 6)
        reasons.append("Shared words: " + ", ".join(sorted(shared)[:4]))

    return min(100.0, score), reasons


def suggest_for(item, limit=6, threshold=30, persist=True):
    """Score `item` against every live item of the opposite kind."""
    pool = (
        Item.objects.live()
        .filter(kind=item.counterpart_kind)
        .exclude(reporter=item.reporter)
        .select_related("category", "location")
    )

    # A found report can only match a loss that happened before it, give or
    # take a day of fuzzy memory.
    if item.kind == Item.LOST:
        pool = pool.filter(happened_on__gte=item.happened_on - timedelta(days=1))
    else:
        pool = pool.filter(happened_on__lte=item.happened_on + timedelta(days=1))

    results = []
    for other in pool[:400]:
        lost, found = (item, other) if item.kind == Item.LOST else (other, item)
        score, reasons = score_pair(lost, found)
        if score >= threshold:
            results.append((other, score, reasons))

    results.sort(key=lambda r: -r[1])
    results = results[:limit]

    if persist:
        for other, score, reasons in results:
            lost, found = (item, other) if item.kind == Item.LOST else (other, item)
            Match.objects.update_or_create(
                lost_item=lost,
                found_item=found,
                defaults={"score": score, "reasons": reasons, "source": Match.SOURCE_RULES},
            )
    return results


def refresh_matches_for(item):
    """Called after a report is filed. Notifies the other side of strong hits."""
    from .models import Notification

    hits = suggest_for(item)
    strong = [h for h in hits if h[1] >= 55]
    if strong:
        item.status = Item.MATCHED
        item.save(update_fields=["status"])
    for other, score, _ in strong:
        Notification.push(
            other.reporter,
            f"A new {item.get_kind_display().lower()} report looks like your {other.title}",
            other.get_absolute_url(),
        )
    return hits
