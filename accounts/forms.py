from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Profile

User = get_user_model()


TEXT_INPUT_CLASSES = (
    "w-full rounded-lg border border-slate-300 px-4 py-3 text-lg "
    "focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
)


class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True)
    # Populated by a tiny inline script via Intl.DateTimeFormat — best-effort;
    # falls back to UTC if JS is disabled. See templates/accounts/signup.html.
    timezone = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = User
        fields = ("email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.HiddenInput):
                continue
            field.widget.attrs.setdefault("class", TEXT_INPUT_CLASSES)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data["email"]
        user.username = email
        user.email = email
        if commit:
            user.save()
            profile = user.profile
            tz = self.cleaned_data.get("timezone")
            if tz:
                profile.timezone = tz
                profile.save(update_fields=["timezone"])
        return user


class ProfileSettingsForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["display_name", "high_contrast_mode"]
        widgets = {
            "display_name": forms.TextInput(attrs={"class": TEXT_INPUT_CLASSES}),
            "high_contrast_mode": forms.CheckboxInput(
                attrs={"class": "h-5 w-5 rounded border-slate-300 text-brand-600"}
            ),
        }


class EmailAuthenticationForm(AuthenticationForm):
    """Django's auth still keys on `username`, but the field is email-shaped for users."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Email"
        self.fields["username"].widget.attrs.update({"autofocus": True, "type": "email"})
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", TEXT_INPUT_CLASSES)
