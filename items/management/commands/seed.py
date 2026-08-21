"""Fill an empty database with categories, campus places and demo reports.

    python manage.py seed          # reference data only
    python manage.py seed --demo   # + fake users, items and a live claim
"""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from claims.models import Claim
from items.matching import refresh_matches_for
from items.models import Category, Item, Location

CATEGORIES = [
    ("Electronics", "electronics", "💻", 10),
    ("Phones", "phones", "📱", 20),
    ("Wallets & cards", "wallets", "👛", 30),
    ("Keys", "keys", "🔑", 40),
    ("Bags & backpacks", "bags", "🎒", 50),
    ("Water bottles", "bottles", "🍶", 60),
    ("Eyewear", "eyewear", "👓", 70),
    ("Books & notes", "books", "📓", 80),
    ("Clothing", "clothing", "🧥", 90),
    ("ID & documents", "id", "🪪", 100),
    ("Jewellery & watches", "jewellery", "⌚", 110),
    ("Cycles", "cycles", "🚲", 120),
    ("Sports gear", "sports", "🏸", 130),
    ("Other", "other", "📦", 999),
]

LOCATIONS = [
    # Academic area
    ("PK Kelkar Library", "ACAD"), ("Lecture Hall Complex", "ACAD"),
    ("New Core Labs", "ACAD"), ("Old Core Labs", "ACAD"),
    ("Faculty Building", "ACAD"), ("Computer Centre", "ACAD"),
    ("CSE Department", "ACAD"), ("Electrical Engineering", "ACAD"),
    ("Mechanical Engineering", "ACAD"), ("Civil Engineering", "ACAD"),
    ("Chemical Engineering", "ACAD"), ("Aerospace Department", "ACAD"),
    ("Physics Department", "ACAD"), ("Mathematics Department", "ACAD"),
    ("Southern Labs", "ACAD"), ("Western Labs", "ACAD"),
    ("Outreach Auditorium", "ACAD"), ("L20 Lecture Hall", "ACAD"),
    # Halls
    ("Hall 1", "HALL"), ("Hall 2", "HALL"), ("Hall 3", "HALL"),
    ("Hall 4", "HALL"), ("Hall 5", "HALL"), ("Hall 6", "HALL"),
    ("Hall 7", "HALL"), ("Hall 8", "HALL"), ("Hall 9", "HALL"),
    ("Hall 10", "HALL"), ("Hall 11", "HALL"), ("Hall 12", "HALL"),
    ("Hall 13", "HALL"), ("Girls Hostel 1", "HALL"),
    ("Girls Hostel 2", "HALL"), ("Girls Hostel Tower", "HALL"),
    # Sports
    ("Gymkhana Grounds", "SPORT"), ("Basketball Court", "SPORT"),
    ("Swimming Pool", "SPORT"), ("Cricket Ground", "SPORT"),
    ("Badminton Hall", "SPORT"), ("Football Ground", "SPORT"),
    ("Health Centre", "SPORT"),
    # Services
    ("New SAC", "SERV"), ("Old SAC", "SERV"), ("Shopping Centre", "SERV"),
    ("Hall 5 Canteen", "SERV"), ("Z Square Food Court", "SERV"),
    ("Bank / ATM area", "SERV"), ("Airstrip Canteen", "SERV"),
    ("Security Office", "SERV"),
    # Open campus
    ("Outside OAT", "OPEN"), ("Main Gate", "OPEN"), ("Bus Stop", "OPEN"),
    ("Airstrip", "OPEN"), ("Nankari", "OPEN"), ("Campus roads", "OPEN"),
    ("Cycle stand", "OPEN"),
]

DEMO_FOUND = [
    ("Black over-ear headphones", "Electronics", "Black", "boAt",
     "Found on a desk on the first floor. Left earcup has a small tear in the padding.",
     "PK Kelkar Library", "There is a faded sticker of a mountain on the headband."),
    ("Brown leather wallet", "Wallets & cards", "Brown", "",
     "Picked up near the entrance. Has cards inside, so I've kept it safe rather than leaving it.",
     "CSE Department", "Contains a library card and about three hundred rupees in tens."),
    ("Black steel water bottle", "Water bottles", "Black", "Nike",
     "Left behind after evening practice. Scratched near the base.",
     "Basketball Court", "Name is written in marker under the base."),
    ("Thin-rim spectacles", "Eyewear", "Black", "",
     "Found in the mess, on the table nearest the window.",
     "Hall 5 Canteen", "One arm has been repaired with clear tape."),
    ("Blue lanyard with keys", "Keys", "Blue", "",
     "Three keys on a blue Techkriti lanyard, found on the path.",
     "Outside OAT", "One key has a small red rubber cap on it."),
]

DEMO_LOST = [
    ("Black HP laptop", "Electronics", "Black", "HP",
     "Left it on a table on the second floor while I went for chai. It's a HP Pavilion, "
     "quite scratched, with a Physics Society sticker on the lid.",
     "PK Kelkar Library"),
    ("Hall 5 room key", "Keys", "Silver", "",
     "Dropped somewhere between the OAT and my hall after the show.",
     "Outside OAT"),
    ("Navy blue backpack", "Bags & backpacks", "Blue", "Wildcraft",
     "Has my notes and a calculator in it. Left it in the lecture hall after the 11am class.",
     "Lecture Hall Complex"),
    ("iPhone 13, black case", "Phones", "Black", "Apple",
     "Lost it around the courts during practice. Lock screen is a photo of a dog.",
     "Basketball Court"),
    ("Black boAt headphones", "Electronics", "Black", "boAt",
     "Left them on a library desk yesterday evening when I packed up in a hurry.",
     "PK Kelkar Library"),
]

DEMO_USERS = [
    ("ankita23@iitk.ac.in", "Ankita Rao", "HALL5", "B-214", "9876543210"),
    ("rohitk22@iitk.ac.in", "Rohit Kumar", "HALL2", "A-108", "9876543211"),
    ("s.mehta24@iitk.ac.in", "S Mehta", "GH1", "C-306", "9876543212"),
    ("devang21@iitk.ac.in", "Devang Patel", "HALL7", "D-011", "9876543213"),
]


class Command(BaseCommand):
    help = "Seed categories, campus locations, and optionally demo content."

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true", help="Also create sample users and reports")

    def handle(self, *args, **opts):
        for name, slug, glyph, order in CATEGORIES:
            Category.objects.get_or_create(
                slug=slug, defaults={"name": name, "glyph": glyph, "order": order}
            )
        self.stdout.write(self.style.SUCCESS(f"{Category.objects.count()} categories"))

        for name, zone in LOCATIONS:
            Location.objects.get_or_create(name=name, defaults={"zone": zone})
        self.stdout.write(self.style.SUCCESS(f"{Location.objects.count()} campus locations"))

        if not opts["demo"]:
            self.stdout.write("Run with --demo for sample reports.")
            return

        User = get_user_model()
        users = []
        for email, name, hall, room, phone in DEMO_USERS:
            u, _ = User.objects.get_or_create(
                email=email,
                defaults={"name": name, "hall": hall, "room": room,
                          "phone": phone, "profile_complete": True},
            )
            users.append(u)
        self.stdout.write(self.style.SUCCESS(f"{len(users)} demo users"))

        today = timezone.localdate()
        made = 0

        for i, (title, cat, colour, brand, desc, loc, secret) in enumerate(DEMO_FOUND):
            item, created = Item.objects.get_or_create(
                title=title, kind=Item.FOUND,
                defaults={
                    "category": Category.objects.get(name=cat),
                    "colour": colour, "brand": brand, "description": desc,
                    "location": Location.objects.get(name=loc),
                    "secret_detail": secret,
                    "handover": "WITH_ME",
                    "happened_on": today - timedelta(days=random.randint(0, 3)),
                    "reporter": users[i % len(users)],
                },
            )
            if created:
                made += 1

        for i, (title, cat, colour, brand, desc, loc) in enumerate(DEMO_LOST):
            item, created = Item.objects.get_or_create(
                title=title, kind=Item.LOST,
                defaults={
                    "category": Category.objects.get(name=cat),
                    "colour": colour, "brand": brand, "description": desc,
                    "location": Location.objects.get(name=loc),
                    "happened_on": today - timedelta(days=random.randint(1, 4)),
                    "reporter": users[(i + 2) % len(users)],
                },
            )
            if created:
                made += 1
                refresh_matches_for(item)

        self.stdout.write(self.style.SUCCESS(f"{made} demo reports"))

        # One claim already in flight, so the workflow is visible immediately.
        wallet = Item.objects.filter(title="Brown leather wallet").first()
        if wallet:
            claimant = next(u for u in users if u != wallet.reporter)
            claim, created = Claim.objects.get_or_create(
                item=wallet, claimant=claimant,
                defaults={"proof": "It's a brown bifold. There's a library card inside and "
                                   "roughly three hundred rupees, mostly in ten-rupee notes."},
            )
            if created:
                claim.advance(Claim.VERIFICATION, wallet.reporter, note="Asked for more proof")
                self.stdout.write(self.style.SUCCESS("1 demo claim in progress"))

        self.stdout.write(self.style.SUCCESS("\nSeeded. Sign in as any @iitk.ac.in address — "
                                             "the code prints in this terminal."))
