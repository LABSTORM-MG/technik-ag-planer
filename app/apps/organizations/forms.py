from django import forms

from .permissions import Role

ROLE_CHOICES_FOR_INVITE = [(r.value, r.label) for r in Role if r != Role.OWNER]


class InviteForm(forms.Form):
    email = forms.EmailField(
        label="E-Mail-Adresse", widget=forms.EmailInput(attrs={"autocomplete": "off"})
    )
    role = forms.ChoiceField(label="Rolle", choices=ROLE_CHOICES_FOR_INVITE, initial=Role.STUDENT)


class RoleForm(forms.Form):
    role = forms.ChoiceField(label="Rolle", choices=ROLE_CHOICES_FOR_INVITE)


class TransferOwnershipForm(forms.Form):
    membership = forms.ModelChoiceField(
        label="Neuer Owner", queryset=None, empty_label="Mitglied wählen"
    )

    def __init__(self, *args, organization, current, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Membership

        self.fields["membership"].queryset = (
            Membership.objects.for_org(organization)
            .exclude(pk=current.pk)
            .exclude(role=Role.TEACHER)
            .select_related("user")
        )
        self.fields["membership"].label_from_instance = lambda m: (
            f"{m.user} ({m.get_role_display()})"
        )


class DissolveForm(forms.Form):
    confirm_name = forms.CharField(
        label="Name der AG zur Bestätigung", widget=forms.TextInput(attrs={"autocomplete": "off"})
    )


class SchoolYearForm(forms.Form):
    confirm = forms.BooleanField(
        label="Ja, alle Jahrgangsstufen jetzt um eins erhöhen.",
        error_messages={"required": "Bitte bestätigen."},
    )


class Require2FAForm(forms.Form):
    require_2fa = forms.BooleanField(label="Zwei-Faktor für alle Mitglieder", required=False)
