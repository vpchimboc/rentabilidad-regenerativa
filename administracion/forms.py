from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.models import Group

from administracion.models import ConfiguracionSistema

User = get_user_model()


class UsuarioForm(forms.ModelForm):
    """Alta y edición de usuarios. La contraseña solo se pide al crear."""

    password1 = forms.CharField(label="Contraseña", widget=forms.PasswordInput, required=False,
                                help_text=password_validation.password_validators_help_text_html())
    password2 = forms.CharField(label="Repita la contraseña", widget=forms.PasswordInput, required=False)
    groups = forms.ModelMultipleChoiceField(
        label="Roles", queryset=Group.objects.order_by("name"), required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Los permisos del usuario son la suma de los permisos de sus roles.",
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "is_active", "is_staff", "is_superuser", "groups"]
        labels = {
            "username": "Usuario",
            "first_name": "Nombres",
            "last_name": "Apellidos",
            "email": "Correo electrónico",
            "is_active": "Cuenta activa",
            "is_staff": "Acceso al editor de datos (/admin/)",
            "is_superuser": "Superusuario (todos los permisos)",
        }
        help_texts = {
            "username": "Letras, dígitos y @ . + - _ ; máximo 150 caracteres.",
            "is_superuser": "Concede todos los permisos sin asignarlos. Úselo solo para cuentas de respaldo.",
        }

    def __init__(self, *args, editor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.creando = self.instance.pk is None
        self.fields["email"].required = True
        if self.creando:
            self.fields["password1"].required = True
            self.fields["password2"].required = True
        else:
            del self.fields["password1"]
            del self.fields["password2"]
        # Solo un superusuario puede conceder o retirar la condición de superusuario.
        if not (editor and editor.is_superuser):
            self.fields["is_superuser"].disabled = True
            self.fields["is_superuser"].help_text = "Solo un superusuario puede modificar este campo."

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya existe otro usuario con este correo.")
        return email

    def clean(self):
        datos = super().clean()
        if self.creando:
            p1, p2 = datos.get("password1"), datos.get("password2")
            if p1 and p2 and p1 != p2:
                self.add_error("password2", "Las contraseñas no coinciden.")
            elif p1:
                usuario = User(username=datos.get("username"), email=datos.get("email"),
                               first_name=datos.get("first_name", ""), last_name=datos.get("last_name", ""))
                try:
                    password_validation.validate_password(p1, usuario)
                except forms.ValidationError as error:
                    self.add_error("password1", error)
        return datos

    def save(self, commit=True):
        usuario = super().save(commit=False)
        if self.creando:
            usuario.set_password(self.cleaned_data["password1"])
        if commit:
            usuario.save()
            self.save_m2m()
        return usuario


class ConfiguracionForm(forms.ModelForm):
    SECCIONES = [
        ("Datos generales", "building", ["nombre_sistema", "institucion", "responsable"]),
        ("Moneda y formatos numéricos", "calculator", ["moneda", "simbolo_moneda", "decimales", "formato_numerico"]),
        ("Tratamiento de impuestos", "receipt", ["iva_porcentaje", "impuesto_renta_porcentaje", "participacion_trabajadores"]),
        ("Parámetros financieros y de cálculo", "scale", ["anio_analisis", "umbral_alerta_break_even"]),
        ("Preferencias de visualización", "eye", ["registros_por_pagina"]),
    ]

    class Meta:
        model = ConfiguracionSistema
        exclude = ["actualizado_por"]

    def secciones(self):
        return [(titulo, icono, [self[c] for c in campos]) for titulo, icono, campos in self.SECCIONES]
