"""Configuración del sistema y registro de auditoría."""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ConfiguracionSistema(models.Model):
    """Parámetros generales (registro único).

    Los parámetros tributarios son de referencia para informes: el motor del IRR
    no los usa, de modo que modificarlos nunca altera en silencio un resultado ya
    calculado. Cada cambio queda en la auditoría con su valor anterior.
    """

    SEPARADORES = [("EC", "1.234,56 (uso ecuatoriano)"), ("INT", "1,234.56 (internacional)")]

    # Datos generales
    nombre_sistema = models.CharField(max_length=120, default="Framework de Rentabilidad Regenerativa")
    institucion = models.CharField(max_length=160, default="Universidad Católica de Cuenca")
    responsable = models.CharField(max_length=120, blank=True, default="Norma Liliana Pañi Ochoa")
    # Moneda y formatos
    moneda = models.CharField(max_length=3, default="USD", help_text="Código ISO 4217. Ecuador: USD (dolarización, 2000)")
    simbolo_moneda = models.CharField(max_length=4, default="$")
    decimales = models.PositiveSmallIntegerField(default=2, validators=[MaxValueValidator(4)])
    formato_numerico = models.CharField(max_length=3, choices=SEPARADORES, default="EC")
    # Tratamiento de impuestos (referencia; normativa ecuatoriana vigente)
    iva_porcentaje = models.DecimalField(
        "IVA (%)", max_digits=5, decimal_places=2, default=15,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Tarifa general del IVA en Ecuador: 15 % desde abril de 2024",
    )
    impuesto_renta_porcentaje = models.DecimalField(
        "Impuesto a la renta de sociedades (%)", max_digits=5, decimal_places=2, default=25,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    participacion_trabajadores = models.DecimalField(
        "Participación de trabajadores en utilidades (%)", max_digits=5, decimal_places=2, default=15,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    # Parámetros financieros y de cálculo
    anio_analisis = models.PositiveIntegerField(
        "Año de análisis por defecto", null=True, blank=True,
        help_text="Vacío: el tablero usa el año más reciente con datos",
    )
    umbral_alerta_break_even = models.DecimalField(
        "Alerta si ventas / punto de equilibrio es menor a", max_digits=5, decimal_places=2, default=1,
        validators=[MinValueValidator(0)],
    )
    # Preferencias de visualización
    registros_por_pagina = models.PositiveSmallIntegerField(
        default=25, validators=[MinValueValidator(10), MaxValueValidator(200)]
    )

    actualizado = models.DateTimeField(auto_now=True)
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "configuración del sistema"
        verbose_name_plural = "configuración del sistema"

    def __str__(self):
        return "Configuración del sistema"

    @classmethod
    def actual(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class RegistroActividad(models.Model):
    """Evento auditable. Nunca guarda contraseñas, tokens ni datos personales innecesarios."""

    CREAR, EDITAR, ELIMINAR = "CREAR", "EDITAR", "ELIMINAR"
    ACCIONES = [
        (CREAR, "Creación"),
        (EDITAR, "Edición"),
        (ELIMINAR, "Eliminación"),
        ("ACTIVAR", "Activación"),
        ("DESACTIVAR", "Desactivación"),
        ("PERMISOS", "Cambio de permisos"),
        ("CONFIG", "Cambio de configuración"),
        ("IMPORTAR", "Importación de datos"),
        ("EXPORTAR", "Exportación de datos"),
        ("LOGIN", "Inicio de sesión"),
        ("LOGOUT", "Cierre de sesión"),
        ("LOGIN_FALLIDO", "Inicio de sesión fallido"),
        ("DENEGADO", "Acceso denegado"),
    ]
    RESULTADOS = [("OK", "Correcto"), ("ERROR", "Error"), ("DENEGADO", "Denegado")]

    fecha = models.DateTimeField(auto_now_add=True, db_index=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="actividades"
    )
    accion = models.CharField(max_length=16, choices=ACCIONES, db_index=True)
    entidad = models.CharField(max_length=60, blank=True)
    objeto = models.CharField(max_length=200, blank=True)
    resultado = models.CharField(max_length=8, choices=RESULTADOS, default="OK")
    detalle = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "registro de actividad"
        verbose_name_plural = "registros de actividad"
        permissions = [
            ("administrar_sistema", "Puede administrar usuarios, roles y configuración"),
            ("exportar_datos", "Puede exportar datos"),
        ]

    def __str__(self):
        return f"{self.fecha:%Y-%m-%d %H:%M} · {self.get_accion_display()} · {self.objeto}"


def registrar(accion, usuario=None, entidad="", objeto="", resultado="OK", **detalle):
    """Atajo para crear un evento de auditoría."""
    if usuario is not None and not getattr(usuario, "is_authenticated", False):
        usuario = None
    return RegistroActividad.objects.create(
        accion=accion, usuario=usuario, entidad=entidad[:60], objeto=str(objeto)[:200],
        resultado=resultado, detalle=detalle,
    )
