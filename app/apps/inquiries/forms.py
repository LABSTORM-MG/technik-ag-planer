from django import forms

from apps.productions.forms import DateInput, TimeInput
from apps.productions.models import Category

from .models import TECH_CHOICES, Inquiry


class InquiryForm(forms.ModelForm):
    """Öffentliches Anfrage-Formular: wenige Pflichtfelder, fast alles Freitext."""

    tech_needs = forms.MultipleChoiceField(
        label="Welche Technik brauchen Sie?",
        choices=TECH_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    schedule_link = forms.URLField(
        label="Link zum Ablauf",
        max_length=500,
        required=False,
        assume_scheme="https",
        widget=forms.URLInput(attrs={"placeholder": "https://…"}),
    )
    # Unsichtbares Feld gegen Spam-Programme: Menschen sehen es nicht und lassen es leer
    website = forms.CharField(
        label="Bitte leer lassen",
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}),
    )

    class Meta:
        model = Inquiry
        fields = [
            "requester_name",
            "requester_email",
            "requester_role",
            "event_name",
            "category",
            "date",
            "start_time",
            "end_time",
            "setup_from",
            "teardown_until",
            "location",
            "tech_needs",
            "tech_notes",
            "schedule",
            "schedule_link",
            "contact_name",
            "contact_phone",
        ]
        widgets = {
            "requester_name": forms.TextInput(attrs={"autocomplete": "name"}),
            "requester_email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "date": DateInput(),
            "start_time": TimeInput(),
            "end_time": TimeInput(),
            "setup_from": TimeInput(),
            "teardown_until": TimeInput(),
            "tech_notes": forms.Textarea(attrs={"rows": 3}),
            "schedule": forms.Textarea(attrs={"rows": 4}),
            "contact_phone": forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel"}),
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.for_org(organization)
        self.fields["category"].empty_label = "Bitte wählen (optional)"

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_time"), cleaned.get("end_time")
        if start and end and end <= start:
            self.add_error("end_time", "Das Ende muss nach dem Beginn liegen.")
        return cleaned

    @property
    def is_spam(self):
        return bool(self.cleaned_data.get("website"))


class InquiryLinkForm(forms.Form):
    """Aktion auf der Einstellungsseite."""

    action = forms.ChoiceField(
        choices=[("activate", "Aktivieren"), ("deactivate", "Deaktivieren"), ("renew", "Neu")]
    )
