"""Navegación lateral: solo módulos con pantalla funcional y que el usuario puede usar."""

from django.urls import reverse
from django.utils import timezone

from administracion.permisos import es_administrador


def _grupo(titulo, items, ruta):
    items = [
        {"titulo": t, "url": u, "icono": i, "activo": (ruta == u if u == "/" else ruta.startswith(u))}
        for t, u, i in items
    ]
    return {"titulo": titulo, "items": items}


def navegacion(request):
    ruta = request.path
    grupos = [
        _grupo("General", [
            ("Inicio", "/", "layout-dashboard"),
            ("Emprendimientos", "/emprendimientos/", "building"),
        ], ruta),
        _grupo("Análisis de rentabilidad", [
            ("Framework e indicadores", "/framework/", "layers"),
            ("Escenarios y sensibilidad", "/escenarios/", "sliders"),
            ("Red neuronal (RNA)", "/rna/", "network"),
        ], ruta),
        _grupo("Investigación", [
            ("Validación Delphi", "/delphi/", "list-checks"),
            ("Bibliometría", "/bibliometria/", "book-open"),
        ], ruta),
    ]
    usuario = getattr(request, "user", None)
    if es_administrador(usuario):
        grupos.append(_grupo("Administración", [
            ("Panel de administración", reverse("adm_panel"), "shield"),
            ("Usuarios", reverse("adm_usuarios"), "users"),
            ("Roles y permisos", reverse("adm_roles"), "shield"),
            ("Configuración", reverse("adm_configuracion"), "settings"),
            ("Auditoría", reverse("adm_auditoria"), "history"),
        ], ruta))
        # El panel no debe marcarse activo en las subsecciones.
        panel = grupos[-1]["items"][0]
        panel["activo"] = ruta == panel["url"]
    if usuario is not None and usuario.is_authenticated and usuario.is_staff:
        grupos[-1 if es_administrador(usuario) else 0]["items"].append(
            {"titulo": "Editor de datos", "url": "/admin/", "icono": "database", "activo": False}
        )
    return {"nav_grupos": grupos, "hoy": timezone.localdate()}
