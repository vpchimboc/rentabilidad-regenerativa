"""Control de acceso del módulo de administración.

La interfaz oculta lo que el usuario no puede hacer, pero la decisión real se toma
aquí, en el servidor, en cada petición.
"""

from functools import wraps

from django.contrib.auth import get_user_model
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from administracion.models import registrar

PERMISO_ADMIN = "administracion.administrar_sistema"
PERMISO_EXPORTAR = "administracion.exportar_datos"

# Módulos de la matriz de permisos: etiqueta → (app_label, modelos)
MODULOS = [
    ("Emprendimientos", "emprendimientos", ["emprendimiento", "periodo", "medicion", "evaluacion"]),
    ("Framework e indicadores", "framework", ["dimension", "variable", "indicador"]),
    ("Escenarios", "escenarios", ["escenario"]),
    ("Red neuronal", "rna", ["modelorna"]),
    ("Validación Delphi", "delphi", None),
    ("Bibliometría", "bibliometria", None),
    ("Usuarios y roles", "auth", ["user", "group"]),
]
ACCIONES = [("view", "Consultar"), ("add", "Crear"), ("change", "Editar"), ("delete", "Eliminar")]


def es_administrador(user):
    return bool(user and user.is_authenticated and user.is_active and user.has_perm(PERMISO_ADMIN))


def requiere_permiso(permiso):
    """Exige sesión iniciada y el permiso indicado; registra los accesos denegados."""

    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not (request.user.is_active and request.user.has_perm(permiso)):
                registrar("DENEGADO", request.user, "Acceso", request.path, resultado="DENEGADO",
                          permiso=permiso)
                raise PermissionDenied
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador


requiere_admin = requiere_permiso(PERMISO_ADMIN)


def administradores_activos():
    """Usuarios activos con capacidad de administrar (superusuarios o con el permiso)."""
    return [u for u in get_user_model().objects.filter(is_active=True) if u.has_perm(PERMISO_ADMIN)]


def dejaria_sin_administrador(usuario, *, activo=None, superusuario=None, grupos=None):
    """¿El cambio propuesto dejaría al sistema sin ningún administrador activo?"""
    restantes = [u for u in administradores_activos() if u.pk != usuario.pk]
    if restantes:
        return False
    activo = usuario.is_active if activo is None else activo
    superusuario = usuario.is_superuser if superusuario is None else superusuario
    if not activo:
        return True
    if superusuario:
        return False
    app, codigo = PERMISO_ADMIN.split(".")
    directos = usuario.user_permissions.filter(content_type__app_label=app, codename=codigo).exists()
    grupos = usuario.groups.all() if grupos is None else grupos
    por_grupo = any(
        g.permissions.filter(content_type__app_label=app, codename=codigo).exists() for g in grupos
    )
    return not (directos or por_grupo)
