from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import PasswordChangeForm, PasswordResetForm, SetPasswordForm

from .models import Grade, User


class LoginForm(forms.Form):
    email = forms.EmailField(
        label="E-Mail-Adresse",
        max_length=254,
        widget=forms.EmailInput(
            attrs={
                "autocomplete": "username",
                "autocapitalize": "none",
                "spellcheck": "false",
                "autofocus": True,
            }
        ),
    )
    password = forms.CharField(
        label="Passwort",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )


class TokenForm(forms.Form):
    token = forms.CharField(
        label="Code aus der Authenticator-App",
        min_length=6,
        max_length=8,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
                "pattern": "[0-9]*",
                "autofocus": True,
            }
        ),
    )

    def clean_token(self):
        return self.cleaned_data["token"].replace(" ", "")


class NewPasswordMixin(forms.Form):
    password1 = forms.CharField(
        label="Passwort",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Mindestens 8 Zeichen, nicht nur Ziffern, nicht zu einfach.",
    )
    password2 = forms.CharField(
        label="Passwort wiederholen",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Die beiden Passwörter stimmen nicht überein.")
        elif p1:
            try:
                password_validation.validate_password(p1, self._user_for_validation())
            except forms.ValidationError as error:
                self.add_error("password1", error)
        return cleaned

    def _user_for_validation(self):
        return None


class AcceptInvitationForm(NewPasswordMixin):
    """Neues Konto über eine Einladung: Name, Jahrgangsstufe (außer Lehrkräfte), Passwort."""

    display_name = forms.CharField(
        label="Name",
        max_length=80,
        help_text="Frei wählbar, auch ein Spitzname. So sehen dich die anderen.",
        widget=forms.TextInput(attrs={"autocomplete": "nickname", "autofocus": True}),
    )
    grade = forms.ChoiceField(label="Jahrgangsstufe", choices=[("", "Bitte wählen")])

    field_order = ["display_name", "grade", "password1", "password2"]

    def __init__(self, *args, email, needs_grade, **kwargs):
        super().__init__(*args, **kwargs)
        self.email = email
        if needs_grade:
            self.fields["grade"].choices = [("", "Bitte wählen"), *Grade.selectable()]
        else:
            del self.fields["grade"]

    def _user_for_validation(self):
        return User(email=self.email, display_name=self.cleaned_data.get("display_name", ""))


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["display_name", "grade"]
        help_texts = {"display_name": "Frei wählbar, auch ein Spitzname."}

    def __init__(self, *args, needs_grade, **kwargs):
        super().__init__(*args, **kwargs)
        if needs_grade:
            field = self.fields["grade"]
            field.required = True
            field.choices = [("", "Bitte wählen"), *Grade.selectable()]
            if self.instance.grade == Grade.EXTERN:
                field.choices.append((Grade.EXTERN, Grade.EXTERN.label))
        else:
            del self.fields["grade"]


class GermanPasswordChangeForm(PasswordChangeForm):
    error_messages = {
        **SetPasswordForm.error_messages,
        "password_incorrect": "Das bisherige Passwort ist falsch.",
        "password_mismatch": "Die beiden Passwörter stimmen nicht überein.",
    }


class GermanSetPasswordForm(SetPasswordForm):
    error_messages = {"password_mismatch": "Die beiden Passwörter stimmen nicht überein."}


class EmailPasswordResetForm(PasswordResetForm):
    # Vorübergehend Textfeld statt EmailField, damit die Beispielkonten der Entwicklung nur
    # „owner“ usw. heißen. In M12 wieder auf E-Mail-Eingabe umstellen (Feature-Liste, Abschnitt 16).
    email = forms.CharField(
        label="E-Mail-Adresse",
        max_length=254,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "username",
                "inputmode": "email",
                "autocapitalize": "none",
                "spellcheck": "false",
                "autofocus": True,
            }
        ),
    )


class DeleteAccountForm(forms.Form):
    password = forms.CharField(
        label="Passwort zur Bestätigung",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    confirm = forms.BooleanField(
        label="Ich möchte mein Konto endgültig löschen.",
        error_messages={"required": "Bitte bestätige das Löschen."},
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("Das Passwort ist falsch.")
        return password


class ConfirmPasswordForm(forms.Form):
    password = forms.CharField(
        label="Passwort zur Bestätigung",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("Das Passwort ist falsch.")
        return password
