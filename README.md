# FindIt — Lost & Found for IIT Kanpur
https://findit-production-2bd1.up.railway.app/

A Django web app where students report lost and found items, get matched
automatically, and work through a verified claim-and-handover process.

Everything is built. The AI agent is **not** — the seam it plugs into is
`items/matching.py`, and nothing else in the codebase needs to change when
you add it.

---

## Run it

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed --demo      # categories, 56 campus places, sample reports
python manage.py runserver
```

Open http://127.0.0.1:8000 — you'll be sent straight to the sign-in page.

Enter any `@iitk.ac.in` address. **In development, the emailed code prints
in your terminal**, so no mail server is needed to test.

For the admin dashboard:

```bash
python manage.py createsuperuser
```
Then http://127.0.0.1:8000/admin/

---

## How sign-in works

```
visit any page
   ↓  (not signed in)
enter @iitk.ac.in address  →  6-digit code emailed
   ↓
enter code  →  account created, name guessed from the email id
   ↓  (first time only)
onboarding: name / hall / room / phone
   ↓
the full site
```

- **Login wall.** `accounts/middleware.py` redirects every anonymous request
  to the sign-in page. Only `/admin/`, `/static/` and `/media/` are exempt.
- **No passwords.** Codes are 6 digits, single-use, 10-minute expiry, 5
  attempts, and each new request invalidates the previous code.
- **Stay signed in.** Sessions last 180 days and refresh on every request, so
  people stay logged in until they hit Sign out.
- **Name is locked.** It's guessed from the email id (`ankit.agarwal21@…` →
  "Ankit Agarwal"), shown once during onboarding so they can fix a bad guess,
  then read-only forever. Hall, room, phone and photo stay editable in
  Profile. Staff can correct a name from the admin.

> **Assumption I made:** IITK ids aren't consistently formatted, so a pure
> guess produces junk for ids like `ps23@`. Letting them correct it *once*
> during onboarding is the compromise. If you want it truly untouchable, drop
> `name` from `OnboardingForm.Meta.fields` in `accounts/forms.py`.

---

## What's in it

| Area | Where |
|---|---|
| OTP auth, login wall, profiles | `accounts/` |
| Items, search, matching, notifications | `items/` |
| Claim workflow, messaging, history | `claims/` |
| Design system | `static/css/findit.css` |
| Admin dashboard | free, via `/admin/` |

**Reporting.** Separate forms for lost and found. Found reports ask for a
*verification detail* — something not visible in the photo. It's never shown
publicly; claimants have to describe it from memory. That's what stops the
wrong person walking off with a laptop.

**Claim workflow.** `REQUESTED → VERIFICATION → APPROVED → HANDOVER →
RETURNED`, with `REJECTED` / `WITHDRAWN` as exits. Phone numbers stay hidden
until the holder approves. Every transition is written to `ClaimEvent`, so
the history is auditable. Several people can claim the same item — the
holder picks between them.

**Matching.** Every new report is scored against the opposite board on
category, place, date proximity, colour, brand and shared vocabulary.
Scores over 55% notify the other side automatically.

---

## Where the AI goes

`items/matching.py` exposes one function:

```python
def suggest_for(item, limit=6, threshold=30, persist=True):
    """Returns [(other_item, score, [reasons])] and writes Match rows."""
```

Keep that signature and swap the body. A realistic path:

1. **Embeddings.** Add pgvector, embed `title + description`, replace the
   token-overlap term with cosine similarity. Biggest quality jump for the
   least work.
2. **LLM reranking.** Take the top ~15 candidates and have a model read both
   descriptions, score the pair, and write the `reasons` list. Those strings
   already render on the item page.
3. **Agent tools.** Wrap the existing code as tools — `search_items`,
   `create_match`, `notify_user`, `start_claim`. They map almost one-to-one
   onto functions that already exist in `items/views.py` and
   `claims/models.py`.

The `Match` model already has a `source` field (`RULES` / `AI` / `HUMAN`), so
you can run both and compare.

---

## Moving to Postgres

Set `DATABASE_URL` in `.env`, then `python manage.py migrate`. Nothing else
changes. Do this before adding pgvector.

## Before deploying

- [ ] Real `SECRET_KEY`, `DEBUG=False`, real `ALLOWED_HOSTS`
- [ ] Swap `EMAIL_BACKEND` for real SMTP — otherwise nobody gets a code
- [ ] Postgres instead of SQLite
- [ ] `whitenoise` + `collectstatic` for static files
- [ ] Media files to S3 or a mounted volume (uploads vanish on redeploy otherwise)
- [ ] Rate-limit `/account/login/` — right now someone can spam codes at an address

---

## Team split

| Person | Owns |
|---|---|
| 1 | `templates/` + `static/css/findit.css` — pages, responsive, accessibility |
| 2 | `accounts/` — auth, middleware, profile, real SMTP |
| 3 | `items/` models, search, filters, and `matching.py` scoring |
| 4 | The AI agent replacing `matching.py` internals |
| 5 | `claims/` + admin + notifications + deployment |

P3 and P4 should pair — the agent's search tool wraps P3's query layer.
