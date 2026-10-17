from django import forms
from django.conf import settings

IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp", "image/heic", "image/heif", "image/gif")


class UploadForm(forms.Form):
    file = forms.FileField(label="Datei", help_text="Wird im Google Drive der AG gespeichert.")

    def __init__(self, *args, max_mb=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_mb = max_mb or settings.GOOGLE_UPLOAD_MAX_MB
        self.fields["file"].help_text += f" Höchstens {self.max_mb} MB."

    def clean_file(self):
        file = self.cleaned_data["file"]
        if file.size > self.max_mb * 1024 * 1024:
            raise forms.ValidationError(f"Die Datei ist zu groß (höchstens {self.max_mb} MB).")
        return file


def clean_image(file):
    """Für Defektfotos: nur Bilder."""
    if file and (file.content_type or "") not in IMAGE_TYPES:
        raise forms.ValidationError("Bitte ein Foto (JPG, PNG, WebP oder HEIC) auswählen.")
    return file


def clean_pdf(file, max_mb):
    """Für das öffentliche Anfrage-Formular: nur echte PDFs, begrenzte Größe."""
    if not file:
        return file
    if file.size > max_mb * 1024 * 1024:
        raise forms.ValidationError(f"Die Datei ist zu groß (höchstens {max_mb} MB).")
    head = file.read(5)
    file.seek(0)
    if head != b"%PDF-":
        raise forms.ValidationError("Bitte eine PDF-Datei auswählen.")
    file.content_type = "application/pdf"
    return file
