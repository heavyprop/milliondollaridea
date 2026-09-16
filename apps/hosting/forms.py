from django import forms


class TokenForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        label="Device name",
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. My MacBook",
                "autocomplete": "off",
                "aria-describedby": "device-name-hint",
            }
        ),
    )
    can_write = forms.BooleanField(
        required=False, initial=True, label="Allow publishing"
    )
