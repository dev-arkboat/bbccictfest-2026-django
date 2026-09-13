from django import forms

from .models import Registration


class RegistrationAdminForm(forms.ModelForm):
    """Admin-only form: segments are addable, total auto-calculates.

    Leave ``amount_bdt`` at 0 to auto-fill it with the summed segment
    fees on save; any non-zero value you type is kept as a manual
    override.
    """

    class Meta:
        model = Registration
        fields = [
            "serial_number", "full_name", "email", "phone", "school",
            "class_name", "events", "amount_bdt", "status",
            "team_name", "teammate_name", "teacher_name", "address",
            "user", "checked_in", "admin_note",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
            "admin_note": forms.Textarea(attrs={"rows": 2}),
            "events": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != "events":
                field.widget.attrs.setdefault("class", "form-input")
        if "events" in self.fields:
            events_field = self.fields["events"]
            events_field.queryset = events_field.queryset.order_by("order", "id")
            events_field.label_from_instance = (
                lambda e: f"{e.name} — {'Free' if not e.fee_bdt else f'{e.fee_bdt} BDT'}"
            )
            events_field.help_text = (
                "Tick all segments this participant joined."
            )
        if "school" in self.fields:
            school_field = self.fields["school"]
            school_field.queryset = school_field.queryset.filter(
                is_active=True
            ).order_by("order", "name")
            school_field.empty_label = "Select school (required)"
            school_field.help_text = "Required — pick the participant's school."
        if "amount_bdt" in self.fields:
            self.fields["amount_bdt"].help_text = (
                "Auto-calculated from segments when left at 0; "
                "type any other value to override manually."
            )

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        digits = "".join(c for c in phone if c.isdigit())
        if len(digits) < 10 or len(digits) > 14:
            raise forms.ValidationError("Enter a valid phone number.")
        return phone

    def clean(self):
        cleaned = super().clean()
        events = list(cleaned.get("events") or [])
        if not events:
            self.add_error("events", "Select at least one segment.")
        amount = cleaned.get("amount_bdt") or 0
        if not events:
            return cleaned
        total = sum(e.fee_bdt for e in events)
        # Surface the auto total so admins see what 0 will become.
        if amount == 0:
            cleaned["amount_bdt"] = total
        return cleaned
