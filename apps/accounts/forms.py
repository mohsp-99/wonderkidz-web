from django import forms

from apps.catalog.models import City, District
from apps.core.text import clean_phone, to_en_digits

from .models import User


class PhoneForm(forms.Form):
    phone = forms.CharField(max_length=20, label="شمارهٔ موبایل")

    def clean_phone(self):
        phone = clean_phone(self.cleaned_data["phone"])
        if not phone:
            raise forms.ValidationError("شمارهٔ موبایل معتبر نیست")
        return phone


class OTPForm(forms.Form):
    code = forms.CharField(max_length=8, label="کد تأیید")

    def clean_code(self):
        code = to_en_digits(self.cleaned_data["code"]).strip()
        if not code.isdigit():
            raise forms.ValidationError("کد تأیید باید عددی باشد")
        return code


class AccountForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["display_name", "city", "district", "notify_moderation", "notify_chat", "notify_saved_search"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["city"].queryset = City.objects.filter(is_active=True)
        self.fields["district"].queryset = District.objects.filter(is_active=True, city__is_active=True).select_related("city")
        self.fields["display_name"].required = False
        for f in ("city", "district"):
            self.fields[f].required = False

    def clean(self):
        data = super().clean()
        city, district = data.get("city"), data.get("district")
        if district and city and district.city_id != city.id:
            self.add_error("district", "این محله در شهر انتخاب‌شده نیست")
        if district and not city:
            data["city"] = district.city
        return data
