from django import forms

from .models import NotificationPreference

TIME_INPUT_CLASSES = (
    "w-full rounded-lg border border-slate-300 px-4 py-3 text-lg "
    "focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
)


class NotificationPreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = ["reminder_time", "reminder_enabled"]
        widgets = {
            "reminder_time": forms.TimeInput(
                attrs={"type": "time", "class": TIME_INPUT_CLASSES}
            ),
            "reminder_enabled": forms.CheckboxInput(
                attrs={"class": "h-5 w-5 rounded border-slate-300 text-brand-600"}
            ),
        }
