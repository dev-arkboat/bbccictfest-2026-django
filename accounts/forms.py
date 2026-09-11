from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from schools.models import School

from .models import Profile

User = get_user_model()


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data.get("first_name", "")
        user.last_name = self.cleaned_data.get("last_name", "")
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)
    email = forms.EmailField(required=False)

    class Meta:
        model = Profile
        fields = ["phone", "institution", "class_name", "avatar_url", "bio"]
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = user
        if user is not None:
            self.fields["first_name"].initial = user.first_name
            self.fields["last_name"].initial = user.last_name
            self.fields["email"].initial = user.email

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = self._user or profile.user
        user.first_name = self.cleaned_data.get("first_name", "")
        user.last_name = self.cleaned_data.get("last_name", "")
        email = self.cleaned_data.get("email", "")
        if email:
            user.email = email
        if commit:
            user.save()
            profile.save()
        return profile


class CampusAmbassadorCreateForm(forms.Form):
    """Organizer-only form that creates a CA user + profile in one go.

    There is no public application flow: organizers create ambassadors here
    (or in Django admin) with a hand-picked username, school and password.
    """

    username = forms.CharField(max_length=150, help_text="Login name the ambassador will use.")
    password1 = forms.CharField(
        label="Password", widget=forms.PasswordInput, help_text="Share this with the ambassador securely."
    )
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=20, required=False)
    school = forms.ModelChoiceField(
        queryset=School.objects.filter(is_active=True).order_by("order", "name"),
        empty_label="Select their school",
        help_text="Required — the ambassador only ever sees this school.",
    )
    bio = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}), required=False,
        help_text="Short public bio shown on their ambassador page (optional).",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-input")

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise ValidationError("Username is required.")
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("This username is already taken.")
        return username

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1") or ""
        password2 = cleaned.get("password2") or ""
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "The two passwords do not match.")
        elif password1:
            try:
                validate_password(password1)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned
