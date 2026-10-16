from django import forms

from .models import MAX_LENGTH


class MessageForm(forms.Form):
    text = forms.CharField(
        label="Nachricht",
        max_length=MAX_LENGTH,
        strip=True,
        widget=forms.Textarea(
            attrs={"rows": 1, "placeholder": "Nachricht schreiben …", "autocomplete": "off"}
        ),
        error_messages={"required": "Die Nachricht ist leer."},
    )
