from django import forms

from .models import Claim, ClaimMessage


class ClaimForm(forms.ModelForm):
    class Meta:
        model = Claim
        fields = ["proof"]
        widgets = {
            "proof": forms.Textarea(attrs={
                "rows": 5,
                "placeholder": "It has a dented lid and a Physics Soc sticker on the back. "
                               "The lock screen is a photo of a dog.",
                "autofocus": True,
            })
        }

    def clean_proof(self):
        proof = self.cleaned_data["proof"].strip()
        if len(proof) < 25:
            raise forms.ValidationError(
                "Add more detail — the finder needs something to check against."
            )
        return proof


class MessageForm(forms.ModelForm):
    class Meta:
        model = ClaimMessage
        fields = ["body"]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 2, "placeholder": "Write a message…"})
        }
        labels = {"body": ""}


class HandoverForm(forms.ModelForm):
    class Meta:
        model = Claim
        fields = ["handover_plan"]
        labels = {"handover_plan": "Where and when"}
        widgets = {
            "handover_plan": forms.TextInput(
                attrs={"placeholder": "Hall 5 gate, today around 7pm"}
            )
        }
