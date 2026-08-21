from django import forms
from django.utils import timezone

from .models import Category, Item, Location


class MultiFileInput(forms.ClearableFileInput):
    """Django blocks `multiple` on the stock widget. We handle the list
    ourselves in the view via request.FILES.getlist('photos')."""

    allow_multiple_selected = True


class ItemForm(forms.ModelForm):
    photos = forms.ImageField(
        required=False,
        widget=MultiFileInput(attrs={"multiple": True, "accept": "image/*"}),
        label="Photos",
        help_text="Up to four. A photo roughly doubles the chance of a match.",
    )

    class Meta:
        model = Item
        fields = [
            "title", "category", "colour", "brand", "description",
            "location", "place_detail", "happened_on", "happened_at",
            "handover", "secret_detail",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Black HP laptop"}),
            "colour": forms.TextInput(attrs={"placeholder": "Black"}),
            "brand": forms.TextInput(attrs={"placeholder": "HP"}),
            "description": forms.Textarea(attrs={"rows": 4}),
            "place_detail": forms.TextInput(
                attrs={"placeholder": "Second floor reading room, near the window"}
            ),
            "happened_on": forms.DateInput(attrs={"type": "date"}),
            "happened_at": forms.TimeInput(attrs={"type": "time"}),
            "secret_detail": forms.TextInput(
                attrs={"placeholder": "A cracked corner, a sticker, what's in the front pocket"}
            ),
        }

    def __init__(self, *args, kind=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.kind = kind or (self.instance.kind if self.instance.pk else Item.LOST)
        self.fields["category"].queryset = Category.objects.all()
        self.fields["category"].empty_label = "Pick a category"
        self.fields["location"].queryset = Location.objects.all()
        self.fields["location"].empty_label = "Pick a place"

        if self.kind == Item.LOST:
            self.fields["happened_on"].label = "When did you lose it?"
            self.fields["location"].label = "Where do you think you lost it?"
            self.fields["description"].label = "Describe it"
            self.fields["description"].help_text = (
                "The more specific you are, the better the matches. Marks, "
                "stickers, contents, anything unusual."
            )
            del self.fields["handover"]
            del self.fields["secret_detail"]
        else:
            self.fields["happened_on"].label = "When did you find it?"
            self.fields["location"].label = "Where did you find it?"
            self.fields["description"].label = "Describe it"
            self.fields["description"].help_text = (
                "Leave out one identifying detail — put that in the field below."
            )
            self.fields["handover"].label = "Where is it now?"
            self.fields["handover"].required = True

        for name, field in self.fields.items():
            if name in ("colour", "brand", "place_detail", "happened_at", "photos", "secret_detail"):
                field.required = False

    def clean_happened_on(self):
        when = self.cleaned_data["happened_on"]
        if when > timezone.localdate():
            raise forms.ValidationError("That date is in the future.")
        return when


class ItemFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "Search items, brands, places…",
            "autocomplete": "off",
        }),
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(), required=False, empty_label="All categories"
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.all(), required=False, empty_label="Anywhere on campus"
    )
    days = forms.ChoiceField(
        required=False,
        choices=[("", "Any time"), ("1", "Today"), ("3", "Last 3 days"),
                 ("7", "Last week"), ("30", "Last month")],
    )
