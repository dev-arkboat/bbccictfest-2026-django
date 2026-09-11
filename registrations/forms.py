from django import forms

from schools.models import School

from .models import CampusAmbassadorApplication, Event, Registration


class RegistrationForm(forms.ModelForm):
    class Meta:
        model = Registration
        fields = [
            "full_name", "email", "phone", "school", "class_name",
            "address", "serial_number",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", "form-input")
        self.fields["school"].empty_label = "Select your school"
        # Required on the form (drives CA rosters + fest-day search) even
        # though legacy rows may predate it, hence blank=True on the model.
        self.fields["school"].required = True
        self.fields["class_name"].widget.attrs.setdefault("class", "form-input")

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        digits = "".join(c for c in phone if c.isdigit())
        if len(digits) < 10 or len(digits) > 14:
            raise forms.ValidationError("Enter a valid phone number.")
        return phone

    def clean_serial_number(self):
        serial = (self.cleaned_data.get("serial_number") or "").strip() or None
        if serial and Registration.objects.filter(serial_number=serial).exclude(
            pk=self.instance.pk if self.instance else None
        ).exists():
            raise forms.ValidationError("This serial number is already registered.")
        return serial

    def save(self, commit=True):
        reg = super().save(commit=False)
        # The school dropdown is the source of truth for institution.
        if reg.school_id:
            reg.institution = reg.school.name
        if commit:
            reg.save()
        return reg


class MultiEventRegistrationForm(forms.Form):
    """One personal-details block + segment checkboxes for the combined page.

    Creates one Registration row per chosen segment; rows made together share
    a group_id so a single bKash payment covers the summed fee.
    """

    full_name = forms.CharField(max_length=160)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20)
    school = forms.ModelChoiceField(
        queryset=School.objects.filter(is_active=True).order_by("order", "name"),
        empty_label="Select your school",
    )
    class_name = forms.ChoiceField(choices=Registration.CLASS_CHOICES)
    address = forms.CharField(max_length=255, required=False)
    events = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        live = list(Event.objects.filter(is_active=True))
        self._live_events = {str(e.pk): e for e in live}
        self.fields["events"].choices = [
            (str(e.pk), f"{e.name} — {'Free' if e.is_free else f'{e.fee_bdt} BDT'}")
            for e in live
        ]
        for name, field in self.fields.items():
            if name != "events":
                field.widget.attrs.setdefault("class", "form-input")

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        digits = "".join(c for c in phone if c.isdigit())
        if len(digits) < 10 or len(digits) > 14:
            raise forms.ValidationError("Enter a valid phone number.")
        return phone

    def clean_events(self):
        chosen = [
            self._live_events[pk]
            for pk in (self.cleaned_data.get("events") or [])
            if pk in self._live_events
        ]
        if not chosen:
            raise forms.ValidationError("Select at least one segment.")
        return chosen


class CampusAmbassadorForm(forms.ModelForm):
    class Meta:
        model = CampusAmbassadorApplication
        fields = [
            "full_name", "email", "phone", "school", "class_name",
            "district", "motivation", "facebook_url",
        ]
        widgets = {
            "motivation": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-input")
        self.fields["motivation"].label = "About You"

    def save(self, commit=True):
        # The form no longer asks for institution separately — the required
        # school selection is the source of truth, mirrored onto the record
        # so admin search, emails and legacy displays keep working.
        app = super().save(commit=False)
        if app.school_id:
            app.institution = app.school.name
        if commit:
            app.save()
        return app
