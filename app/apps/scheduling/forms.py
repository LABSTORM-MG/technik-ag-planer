import json
from datetime import timedelta

from django import forms

from apps.organizations.models import Membership

from .models import Event, EventAttendee, EventSeries, Unavailability
from .periods import periods_for
from .services import MAX_SERIES_DAYS


class SegmentedRadio(forms.RadioSelect):
    """Auswahl als Schalter im Stil von `.segmented`, weiterhin echte Radio-Felder."""

    template_name = "productions/widgets/segmented.html"
    option_template_name = "productions/widgets/segmented_option.html"


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%d", **kwargs)


class TimeInput(forms.TimeInput):
    input_type = "time"

    def __init__(self, **kwargs):
        super().__init__(format="%H:%M", **kwargs)


class PeriodTimesMixin:
    """Zeiten wahlweise als Uhrzeit oder als Schulstunde („ab der 5. Stunde“).

    Für jedes Zeitfeld (z. B. start_time) entsteht ein Auswahlfeld start_period. Ist eine
    Stunde gewählt, rechnet das Formular sie über das Stundenraster in die Uhrzeit um –
    auch ohne JavaScript. Mit JavaScript wird das Zeitfeld sofort mit ausgefüllt.
    """

    period_fields = {"start_time": "start", "end_time": "end"}

    def setup_periods(self, organization):
        periods = periods_for(organization) if organization is not None else []
        self.period_names = {}
        if not periods:
            return
        mapping = {str(p.number): [f"{p.start_time:%H:%M}", f"{p.end_time:%H:%M}"] for p in periods}
        choices = [("", "–")] + [(str(p.number), p.label) for p in periods]
        for time_field, edge in self.period_fields.items():
            if time_field not in self.fields:
                continue
            name = time_field.replace("_time", "_period")
            self.period_names[time_field] = name
            self.fields[name] = forms.ChoiceField(
                label="oder Stunde",
                choices=choices,
                required=False,
                widget=forms.Select(
                    attrs={
                        "data-period-edge": edge,
                        "data-period-target": self[time_field].auto_id,
                        "data-period-map": json.dumps(mapping),
                    }
                ),
            )
        if self.is_bound:
            data = self.data.copy()
            for time_field, name in self.period_names.items():
                number = data.get(self.add_prefix(name))
                if number in mapping:
                    data[self.add_prefix(time_field)] = mapping[number][
                        0 if self.period_fields[time_field] == "start" else 1
                    ]
            self.data = data

    def period_field(self, time_field):
        name = getattr(self, "period_names", {}).get(time_field)
        return self[name] if name else None


class EventForm(PeriodTimesMixin, forms.ModelForm):
    repeat = forms.ChoiceField(
        label="Wiederholen",
        required=False,
        choices=[("", "Nicht wiederholen"), *EventSeries.Frequency.choices],
    )
    until = forms.DateField(
        label="Wiederholen bis",
        required=False,
        widget=DateInput(),
        help_text="z. B. bis zum Schuljahresende",
    )

    class Meta:
        model = Event
        fields = ["title", "date", "start_time", "end_time", "location", "notes"]
        widgets = {
            "title": forms.TextInput(attrs={"autofocus": True}),
            "date": DateInput(),
            "start_time": TimeInput(),
            "end_time": TimeInput(),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {"start_time": "Leer lassen für ganztägig"}

    def __init__(self, *args, organization, allow_repeat=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_periods(organization)
        if not allow_repeat:
            del self.fields["repeat"]
            del self.fields["until"]

    def clean(self):
        cleaned = super().clean()
        if self.fields.get("repeat") and cleaned.get("repeat"):
            until, day = cleaned.get("until"), cleaned.get("date")
            if not until:
                self.add_error("until", "Bitte ein Enddatum für die Wiederholung angeben.")
            elif day and until < day:
                self.add_error("until", "Das Enddatum muss nach dem ersten Termin liegen.")
            elif day and until > day + timedelta(days=MAX_SERIES_DAYS):
                self.add_error("until", "Serien sind höchstens etwa ein Schuljahr lang.")
        return cleaned


class EventEditScopeForm(forms.Form):
    scope = forms.ChoiceField(
        label="Ändern für",
        choices=[("single", "Nur diesen Termin"), ("following", "Diesen und alle folgenden")],
        initial="single",
        widget=SegmentedRadio,
    )


class AttendeeForm(forms.Form):
    membership = forms.ModelChoiceField(
        queryset=None, label="Mitglied", empty_label="Mitglied wählen"
    )
    status = forms.ChoiceField(
        label="Art",
        choices=[
            (EventAttendee.Status.REQUESTED, "Anfragen"),
            (EventAttendee.Status.CONFIRMED, "Direkt einteilen"),
        ],
        initial=EventAttendee.Status.REQUESTED,
        widget=SegmentedRadio,
    )
    ignore_conflicts = forms.BooleanField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, event, **kwargs):
        super().__init__(*args, **kwargs)
        taken = event.attendees.values_list("membership_id", flat=True)
        self.fields["membership"].queryset = (
            Membership.objects.for_org(event.organization)
            .exclude(pk__in=taken)
            .select_related("user")
            .order_by("user__display_name")
        )
        self.fields["membership"].label_from_instance = lambda m: str(m.user)


class UnavailabilityForm(PeriodTimesMixin, forms.ModelForm):
    class Meta:
        model = Unavailability
        fields = ["start_date", "start_time", "end_date", "end_time", "note"]
        widgets = {
            "start_date": DateInput(attrs={"autofocus": True}),
            "end_date": DateInput(),
            "start_time": TimeInput(),
            "end_time": TimeInput(),
        }
        labels = {"start_time": "ab (Uhrzeit)", "end_time": "bis (Uhrzeit)"}
        help_texts = {"start_time": "Ohne Uhrzeit gilt der ganze Tag."}

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_periods(organization)


class PeriodForm(forms.Form):
    start_time = forms.TimeField(label="Beginn", widget=TimeInput())
    end_time = forms.TimeField(label="Ende", widget=TimeInput())


class BasePeriodFormSet(forms.BaseFormSet):
    """Die Stunden werden nach Beginn sortiert und beim Speichern durchnummeriert."""

    def clean(self):
        super().clean()
        rows = []
        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue
            data = getattr(form, "cleaned_data", None)
            if not data or "start_time" not in data or "end_time" not in data:
                continue
            if data["end_time"] <= data["start_time"]:
                form.add_error("end_time", "Das Ende muss nach dem Beginn liegen.")
                continue
            rows.append((data["start_time"], data["end_time"]))
        rows.sort()
        for (_start, end), (next_start, _end) in zip(rows, rows[1:], strict=False):
            if next_start < end:
                raise forms.ValidationError("Die Stunden dürfen sich nicht überschneiden.")
        self.rows = rows


PeriodFormSet = forms.formset_factory(
    PeriodForm, formset=BasePeriodFormSet, extra=0, can_delete=True
)
