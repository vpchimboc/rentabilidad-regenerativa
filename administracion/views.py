from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.forms.models import model_to_dict
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from administracion.forms import ConfiguracionForm, UsuarioForm
from administracion.models import ConfiguracionSistema, RegistroActividad, registrar
from administracion.permisos import (
    ACCIONES, MODULOS, PERMISO_ADMIN, administradores_activos, dejaria_sin_administrador,
    requiere_admin,
)
from emprendimientos.models import Emprendimiento, Periodo
from framework.models import Indicador
from rna.models import ModeloRNA

User = get_user_model()


def _por_pagina():
    return ConfiguracionSistema.actual().registros_por_pagina


def _alertas_integridad():
    """Comprobaciones que se pueden verificar de forma fiable."""
    alertas = []
    for u in User.objects.filter(is_active=True, is_superuser=True):
        if u.check_password(u.username) or u.check_password("admin"):
            alertas.append(("error", f"La cuenta «{u.username}» conserva una contraseña por defecto. Cámbiela.",
                            "users"))
    if settings.DEBUG:
        alertas.append(("warning", "El sistema funciona en modo de desarrollo (DEBUG). "
                        "No lo exponga fuera de este equipo.", "settings"))
    if "insecure" in settings.SECRET_KEY:
        alertas.append(("warning", "La clave secreta es la de desarrollo; reemplácela antes de publicar.",
                        "shield"))
    if len(administradores_activos()) == 1:
        alertas.append(("info", "Solo hay un administrador activo. Conviene una segunda cuenta de respaldo.",
                        "users"))
    sin_periodo = Emprendimiento.objects.filter(periodos__isnull=True).count()
    if sin_periodo:
        alertas.append(("info", f"{sin_periodo} emprendimientos no tienen ningún período con datos financieros.",
                        "building"))
    sin_medicion = Periodo.objects.filter(mediciones__isnull=True).count()
    if sin_medicion:
        alertas.append(("info", f"{sin_medicion} períodos no tienen mediciones de indicadores.", "chart-line"))
    for ind in Indicador.objects.all():
        cortes = ind.cortes
        orden = sorted(cortes) if ind.direccion == ind.MAYOR_MEJOR else sorted(cortes, reverse=True)
        if cortes != orden:
            alertas.append(("error", f"Los cortes del indicador {ind.codigo} no están ordenados.", "scale"))
    if not ModeloRNA.objects.filter(activo=True).exists():
        alertas.append(("info", "No hay un modelo de red neuronal entrenado.", "network"))
    return alertas


@requiere_admin
def panel(request):
    usuarios = User.objects.aggregate(
        total=Count("id"), activos=Count("id", filter=Q(is_active=True)),
    )
    importaciones = RegistroActividad.objects.filter(accion="IMPORTAR")
    fuentes = (
        Emprendimiento.objects.values("fuente").annotate(n=Count("id")).order_by("-n")
    )
    return render(request, "administracion/panel.html", {
        "usuarios": usuarios,
        "inactivos": usuarios["total"] - usuarios["activos"],
        "roles": Group.objects.count(),
        "permisos_asignados": Group.permissions.through.objects.count(),
        "emprendimientos": Emprendimiento.objects.count(),
        "ultima_importacion": importaciones.first(),
        "importaciones": importaciones.count(),
        "fuentes": fuentes,
        "actividad": RegistroActividad.objects.select_related("usuario")[:8],
        "alertas": _alertas_integridad(),
    })


@requiere_admin
def usuarios(request):
    qs = User.objects.prefetch_related("groups").order_by("username")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(first_name__icontains=q)
                       | Q(last_name__icontains=q) | Q(email__icontains=q))
    rol = request.GET.get("rol", "")
    if rol.isdigit():
        qs = qs.filter(groups__id=int(rol))
    estado = request.GET.get("estado", "")
    if estado in ("activo", "inactivo"):
        qs = qs.filter(is_active=(estado == "activo"))
    pagina = Paginator(qs, _por_pagina()).get_page(request.GET.get("pagina"))
    filtros = request.GET.copy()
    filtros.pop("pagina", None)
    return render(request, "administracion/usuarios.html", {
        "pagina": pagina, "q": q, "rol": rol, "estado": estado,
        "roles": Group.objects.order_by("name"), "filtros": filtros.urlencode(),
        "total": qs.count(),
    })


def _guardar_usuario(request, instancia=None):
    form = UsuarioForm(request.POST or None, instance=instancia, editor=request.user)
    if request.method == "POST" and form.is_valid():
        datos = form.cleaned_data
        if instancia is not None and dejaria_sin_administrador(
            instancia, activo=datos["is_active"], superusuario=datos.get("is_superuser", instancia.is_superuser),
            grupos=datos["groups"],
        ):
            form.add_error(None, "El cambio dejaría al sistema sin ningún administrador activo.")
        else:
            usuario = form.save()
            messages.success(request, f"Usuario «{usuario.username}» guardado.")
            return redirect("adm_usuarios")
    return render(request, "administracion/usuario_form.html", {"form": form, "objeto": instancia})


@requiere_admin
def usuario_crear(request):
    return _guardar_usuario(request)


@requiere_admin
def usuario_editar(request, pk):
    return _guardar_usuario(request, get_object_or_404(User, pk=pk))


@requiere_admin
def usuario_estado(request, pk):
    """Activa o desactiva una cuenta, previa confirmación explícita."""
    usuario = get_object_or_404(User, pk=pk)
    activar = not usuario.is_active
    error = None
    if not activar and usuario.pk == request.user.pk:
        error = "No puede desactivar su propia cuenta mientras la está usando."
    elif not activar and dejaria_sin_administrador(usuario, activo=False):
        error = "Es el último administrador activo: desactivarlo bloquearía el sistema."
    if request.method == "POST" and request.POST.get("confirmado") == "1" and not error:
        usuario.is_active = activar
        usuario.save(update_fields=["is_active"])
        registrar("ACTIVAR" if activar else "DESACTIVAR", request.user, "Usuario", usuario.username)
        messages.success(request, f"Cuenta «{usuario.username}» {'activada' if activar else 'desactivada'}.")
        return redirect("adm_usuarios")
    return render(request, "administracion/confirmar.html", {
        "titulo": f"{'Activar' if activar else 'Desactivar'} la cuenta «{usuario.username}»",
        "texto": ("La persona podrá volver a iniciar sesión." if activar else
                  "La persona no podrá iniciar sesión. Sus registros e historial se conservan."),
        "boton": "Activar cuenta" if activar else "Desactivar cuenta",
        "peligro": not activar,
        "error": error,
        "volver": "adm_usuarios",
    })


def _matriz(grupo=None):
    """Filas por módulo con los permisos estándar de Django por acción."""
    asignados = set(grupo.permissions.values_list("id", flat=True)) if grupo else set()
    filas = []
    for etiqueta, app, modelos in MODULOS:
        celdas = []
        for accion, nombre in ACCIONES:
            filtro = Q(content_type__app_label=app, codename__startswith=f"{accion}_")
            if modelos:
                filtro &= Q(content_type__model__in=modelos)
            ids = list(Permission.objects.filter(filtro).values_list("id", flat=True))
            celdas.append({
                "accion": accion, "nombre": nombre, "ids": ids,
                "marcado": bool(ids) and set(ids) <= asignados,
                "parcial": bool(set(ids) & asignados) and not set(ids) <= asignados,
                "clave": f"{app}:{accion}",
            })
        filas.append({"modulo": etiqueta, "celdas": celdas})
    especiales = list(Permission.objects.filter(
        content_type__app_label="administracion",
        codename__in=["exportar_datos", "administrar_sistema"],
    ).order_by("codename"))
    return filas, [{"permiso": p, "marcado": p.id in asignados} for p in especiales]


@requiere_admin
def roles(request):
    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        if not nombre:
            messages.error(request, "Escriba un nombre para el rol.")
        elif Group.objects.filter(name__iexact=nombre).exists():
            messages.error(request, f"Ya existe el rol «{nombre}».")
        else:
            grupo = Group.objects.create(name=nombre[:150])
            messages.success(request, f"Rol «{grupo.name}» creado. Asigne ahora sus permisos.")
            return redirect("adm_rol", pk=grupo.pk)
    grupos = Group.objects.annotate(n_usuarios=Count("user", distinct=True),
                                    n_permisos=Count("permissions", distinct=True)).order_by("name")
    return render(request, "administracion/roles.html", {"grupos": grupos})


@requiere_admin
def rol(request, pk):
    grupo = get_object_or_404(Group, pk=pk)
    filas, especiales = _matriz(grupo)
    if request.method == "POST":
        nuevos = set()
        marcadas = set(request.POST.getlist("celda"))
        for fila in filas:
            for c in fila["celdas"]:
                if c["clave"] in marcadas:
                    nuevos.update(c["ids"])
        especiales_ids = {e["permiso"].id for e in especiales}
        nuevos.update(int(i) for i in request.POST.getlist("especial") if i.isdigit() and int(i) in especiales_ids)
        quita_admin = any(e["marcado"] and e["permiso"].codename == "administrar_sistema"
                          and e["permiso"].id not in nuevos for e in especiales)
        if quita_admin and _rol_sostiene_ultimo_admin(grupo):
            messages.error(request, "Este rol es el único que da acceso de administración a los "
                           "administradores activos. Quitarlo bloquearía el sistema.")
            return redirect("adm_rol", pk=grupo.pk)
        anteriores = set(grupo.permissions.values_list("id", flat=True))
        grupo.permissions.set(nuevos)
        registrar("PERMISOS", request.user, "Rol", grupo.name,
                  concedidos=len(nuevos - anteriores), retirados=len(anteriores - nuevos))
        messages.success(request, f"Permisos del rol «{grupo.name}» actualizados.")
        return redirect("adm_rol", pk=grupo.pk)
    return render(request, "administracion/rol.html", {
        "grupo": grupo, "filas": filas, "especiales": especiales, "acciones": ACCIONES,
        "miembros": grupo.user_set.order_by("username"),
    })


def _rol_sostiene_ultimo_admin(grupo):
    """True si ningún administrador activo conservaría el acceso sin este rol."""
    app, codigo = PERMISO_ADMIN.split(".")
    for u in administradores_activos():
        if u.is_superuser:
            return False
        if u.user_permissions.filter(content_type__app_label=app, codename=codigo).exists():
            return False
        otros = u.groups.exclude(pk=grupo.pk)
        if any(g.permissions.filter(content_type__app_label=app, codename=codigo).exists() for g in otros):
            return False
    return True


@requiere_admin
@require_POST
def rol_eliminar(request, pk):
    grupo = get_object_or_404(Group, pk=pk)
    if grupo.permissions.filter(codename="administrar_sistema").exists() and _rol_sostiene_ultimo_admin(grupo):
        messages.error(request, "No se puede eliminar: es el único rol que mantiene un administrador activo.")
        return redirect("adm_rol", pk=grupo.pk)
    if request.POST.get("confirmado") != "1":
        return render(request, "administracion/confirmar.html", {
            "titulo": f"Eliminar el rol «{grupo.name}»",
            "texto": "Sus usuarios perderán los permisos que les daba este rol. No se puede deshacer.",
            "boton": "Eliminar rol", "peligro": True, "error": None, "volver": "adm_roles",
        })
    nombre = grupo.name
    grupo.delete()
    messages.success(request, f"Rol «{nombre}» eliminado.")
    return redirect("adm_roles")


@requiere_admin
def configuracion(request):
    config = ConfiguracionSistema.actual()
    config.refresh_from_db()  # valores tal como están guardados (p. ej. 1.00, no 1)
    antes = model_to_dict(config, exclude=["id", "actualizado_por"])
    form = ConfiguracionForm(request.POST or None, instance=config)
    if request.method == "POST":
        if form.is_valid():
            cambios = {
                campo: [str(antes[campo]), str(form.cleaned_data[campo])]
                for campo in form.changed_data
            }
            config = form.save(commit=False)
            config.actualizado_por = request.user
            config.save()
            if cambios:
                registrar("CONFIG", request.user, "Configuración", "Parámetros del sistema", cambios=cambios)
                messages.success(request, f"Configuración guardada ({len(cambios)} cambios registrados en auditoría).")
            else:
                messages.info(request, "No había cambios que guardar.")
            return redirect("adm_configuracion")
        messages.error(request, "Revise los campos marcados.")
    return render(request, "administracion/configuracion.html", {"form": form, "config": config})


@requiere_admin
def auditoria(request):
    qs = RegistroActividad.objects.select_related("usuario")
    accion = request.GET.get("accion", "")
    if accion in dict(RegistroActividad.ACCIONES):
        qs = qs.filter(accion=accion)
    usuario = request.GET.get("usuario", "")
    if usuario.isdigit():
        qs = qs.filter(usuario_id=int(usuario))
    desde, hasta = request.GET.get("desde", ""), request.GET.get("hasta", "")
    if desde:
        qs = qs.filter(fecha__date__gte=desde)
    if hasta:
        qs = qs.filter(fecha__date__lte=hasta)
    pagina = Paginator(qs, _por_pagina()).get_page(request.GET.get("pagina"))
    filtros = request.GET.copy()
    filtros.pop("pagina", None)
    return render(request, "administracion/auditoria.html", {
        "pagina": pagina, "acciones": RegistroActividad.ACCIONES, "accion": accion,
        "usuarios": User.objects.order_by("username"), "usuario": usuario,
        "desde": desde, "hasta": hasta, "filtros": filtros.urlencode(),
    })
