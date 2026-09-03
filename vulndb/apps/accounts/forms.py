from __future__ import annotations

from django import forms
from django.contrib.auth.password_validation import validate_password

from vulndb.apps.accounts.models import Role, User


class LocalUserCreateForm(forms.ModelForm):
    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={"class": "input", "autocomplete": "new-password"}),
        min_length=8,
    )
    password2 = forms.CharField(
        label="Повтор пароля",
        widget=forms.PasswordInput(attrs={"class": "input", "autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = ("username", "full_name", "email", "role", "is_verifier", "is_active")
        widgets = {
            "username": forms.TextInput(attrs={"class": "input", "autocomplete": "off"}),
            "full_name": forms.TextInput(attrs={"class": "input"}),
            "email": forms.EmailInput(attrs={"class": "input"}),
            "role": forms.Select(attrs={"class": "select"}),
            "is_verifier": forms.CheckboxInput(attrs={"class": "checkbox"}),
            "is_active": forms.CheckboxInput(attrs={"class": "checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Логин"
        self.fields["full_name"].label = "ФИО"
        self.fields["email"].label = "Email"
        self.fields["role"].label = "Роль"
        self.fields["is_verifier"].label = "Verifier (подтверждение закрытия заявок)"
        self.fields["is_active"].label = "Активен"
        self.fields["is_active"].initial = True
        self.fields["role"].choices = Role.choices

    def clean_username(self) -> str:
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise forms.ValidationError("Укажите логин.")
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Пользователь с таким логином уже есть.")
        return username

    def clean(self):
        data = super().clean()
        p1 = data.get("password") or ""
        p2 = data.get("password2") or ""
        if p1 != p2:
            self.add_error("password2", "Пароли не совпадают.")
        if p1:
            validate_password(p1)
        return data

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        _apply_role_flags(user)
        if commit:
            user.save()
        return user


class LocalUserEditForm(forms.ModelForm):
    password = forms.CharField(
        label="Новый пароль",
        required=False,
        widget=forms.PasswordInput(attrs={"class": "input", "autocomplete": "new-password"}),
        help_text="Оставьте пустым, чтобы не менять.",
    )
    password2 = forms.CharField(
        label="Повтор пароля",
        required=False,
        widget=forms.PasswordInput(attrs={"class": "input", "autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = ("full_name", "email", "role", "is_verifier", "is_active")
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "input"}),
            "email": forms.EmailInput(attrs={"class": "input"}),
            "role": forms.Select(attrs={"class": "select"}),
            "is_verifier": forms.CheckboxInput(attrs={"class": "checkbox"}),
            "is_active": forms.CheckboxInput(attrs={"class": "checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["full_name"].label = "ФИО"
        self.fields["email"].label = "Email"
        self.fields["role"].label = "Роль"
        self.fields["is_verifier"].label = "Verifier (подтверждение закрытия заявок)"
        self.fields["is_active"].label = "Активен"
        self.fields["role"].choices = Role.choices

    def clean(self):
        data = super().clean()
        p1 = data.get("password") or ""
        p2 = data.get("password2") or ""
        if p1 or p2:
            if p1 != p2:
                self.add_error("password2", "Пароли не совпадают.")
            if p1:
                validate_password(p1, user=self.instance)
        return data

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        if self.cleaned_data.get("password"):
            user.set_password(self.cleaned_data["password"])
        _apply_role_flags(user)
        if commit:
            user.save()
        return user


def _apply_role_flags(user: User) -> None:
    if user.role == Role.PLATFORM_ADMIN:
        user.is_staff = True
        user.is_superuser = True
    else:
        user.is_staff = False
        user.is_superuser = False
