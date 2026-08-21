from django import forms
from django.conf import settings

from .models import HALLS, User


class EmailForm(forms.Form):
    email = forms.EmailField(
        label="Institute email",
        widget=forms.EmailInput(attrs={
            "placeholder": "yourid@iitk.ac.in",
            "autofocus": True,
            "autocomplete": "email",
            "inputmode": "email",
        }),
    )

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        domains = getattr(settings, "ALLOWED_EMAIL_DOMAINS", [])
        if domains and email.split("@")[-1] not in domains:
            allowed = " or ".join("@" + d for d in domains)
            raise forms.ValidationError(
                f"FindIt is for the campus only. Use your {allowed} address."
            )
        return email


class CodeForm(forms.Form):
    code = forms.CharField(
        label="6-digit code",
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            "placeholder": "······",
            "autofocus": True,
            "autocomplete": "one-time-code",
            "inputmode": "numeric",
            "pattern": "[0-9]*",
            "class": "otp-input",
        }),
    )

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        if not code.isdigit():
            raise forms.ValidationError("Codes are six digits.")
        return code


class OnboardingForm(forms.ModelForm):
    """Shown once, right after the first successful sign-in."""

    class Meta:
        model = User
        fields = ["name", "hall", "room", "phone"]
        labels = {
            "name": "Your name",
            "hall": "Hall",
            "room": "Room number",
            "phone": "Contact number",
        }
        help_texts = {
            "name": "Pulled from your email id. Fix it now — it is locked afterwards.",
            "phone": "Shown only to someone you are actively returning an item to.",
        }
        widgets = {
            "room": forms.TextInput(attrs={"placeholder": "e.g. B-214"}),
            "phone": forms.TextInput(attrs={
                "placeholder": "10-digit mobile",
                "inputmode": "numeric",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["hall"].choices = [("", "Pick your hall")] + list(HALLS)
        for f in ("name", "hall", "room", "phone"):
            self.fields[f].required = True

    def clean_phone(self):
        phone = "".join(c for c in self.cleaned_data["phone"] if c.isdigit())
        if len(phone) < 10:
            raise forms.ValidationError("Enter a 10-digit mobile number.")
        return phone[-10:]

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        if len(name) < 2:
            raise forms.ValidationError("Enter your name.")
        return name


class ProfileForm(forms.ModelForm):
    """Everything editable later. Name is deliberately absent."""

    class Meta:
        model = User
        fields = ["hall", "room", "phone", "avatar"]
        labels = {
            "hall": "Hall",
            "room": "Room number",
            "phone": "Contact number",
            "avatar": "Photo",
        }
        widgets = {
            "room": forms.TextInput(attrs={"placeholder": "e.g. B-214"}),
            "phone": forms.TextInput(attrs={"inputmode": "numeric"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["hall"].choices = [("", "Pick your hall")] + list(HALLS)
        for f in ("hall", "room", "phone"):
            self.fields[f].required = True

    clean_phone = OnboardingForm.clean_phone
