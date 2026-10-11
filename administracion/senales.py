"""Receptores de auditoría y middleware que expone el usuario de la petición en curso."""

import threading
from contextlib import contextmanager

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_delete, post_save

from administracion.models import RegistroActividad, registrar

_estado = threading.local()

# Modelos cuyo alta, edición o baja se audita. Mediciones y evaluaciones quedan
# fuera: se generan en volumen y su trazabilidad está en el propio período.
AUDITADOS = {
    "emprendimientos.emprendimiento": "Emprendimiento",
    "emprendimientos.periodo": "Período",
    "framework.dimension": "Dimensión",
    "framework.indicador": "Indicador",
    "auth.user": "Usuario",
    "auth.group": "Rol",
}


class UsuarioActualMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _estado.usuario = getattr(request, "user", None)
        try:
            return self.get_response(request)
        finally:
            _estado.usuario = None


def usuario_actual():
    return getattr(_estado, "usuario", None)


@contextmanager
def auditoria_silenciada():
    """Suspende la auditoría por objeto (p. ej. en una importación masiva)."""
    previo = getattr(_estado, "silencio", False)
    _estado.silencio = True
    try:
        yield
    finally:
        _estado.silencio = previo


def _clave(sender):
    return f"{sender._meta.app_label}.{sender._meta.model_name}"


def _al_guardar(sender, instance, created, raw=False, update_fields=None, **kwargs):
    entidad = AUDITADOS.get(_clave(sender))
    if not entidad or raw or getattr(_estado, "silencio", False):
        return
    # Django actualiza last_login en cada ingreso: ya lo cubre el evento LOGIN.
    if update_fields and set(update_fields) <= {"last_login"}:
        return
    registrar(
        RegistroActividad.CREAR if created else RegistroActividad.EDITAR,
        usuario_actual(), entidad, instance,
    )


def _al_eliminar(sender, instance, **kwargs):
    entidad = AUDITADOS.get(_clave(sender))
    if entidad and not getattr(_estado, "silencio", False):
        registrar(RegistroActividad.ELIMINAR, usuario_actual(), entidad, instance)


post_save.connect(_al_guardar, dispatch_uid="auditoria_guardar")
post_delete.connect(_al_eliminar, dispatch_uid="auditoria_eliminar")


def _login(sender, request, user, **kwargs):
    registrar("LOGIN", user, "Sesión", user.get_username())


def _logout(sender, request, user, **kwargs):
    if user is not None:
        registrar("LOGOUT", user, "Sesión", user.get_username())


def _login_fallido(sender, credentials, request=None, **kwargs):
    # Solo el nombre de usuario intentado: jamás la contraseña.
    registrar("LOGIN_FALLIDO", None, "Sesión", credentials.get("username", "")[:60], resultado="ERROR")


user_logged_in.connect(_login, dispatch_uid="auditoria_login")
user_logged_out.connect(_logout, dispatch_uid="auditoria_logout")
user_login_failed.connect(_login_fallido, dispatch_uid="auditoria_login_fallido")
