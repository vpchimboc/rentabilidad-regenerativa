from django.urls import path

from administracion import views

urlpatterns = [
    path("", views.panel, name="adm_panel"),
    path("usuarios/", views.usuarios, name="adm_usuarios"),
    path("usuarios/nuevo/", views.usuario_crear, name="adm_usuario_crear"),
    path("usuarios/<int:pk>/", views.usuario_editar, name="adm_usuario_editar"),
    path("usuarios/<int:pk>/estado/", views.usuario_estado, name="adm_usuario_estado"),
    path("roles/", views.roles, name="adm_roles"),
    path("roles/<int:pk>/", views.rol, name="adm_rol"),
    path("roles/<int:pk>/eliminar/", views.rol_eliminar, name="adm_rol_eliminar"),
    path("configuracion/", views.configuracion, name="adm_configuracion"),
    path("auditoria/", views.auditoria, name="adm_auditoria"),
]
