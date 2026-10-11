from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("cuenta/ingresar/", auth_views.LoginView.as_view(redirect_authenticated_user=True), name="login"),
    path("cuenta/salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("administracion/", include("administracion.urls")),
    path("", include("core.urls")),
    path("framework/", include("framework.urls")),
    path("emprendimientos/", include("emprendimientos.urls")),
    path("escenarios/", include("escenarios.urls")),
    path("rna/", include("rna.urls")),
    path("delphi/", include("delphi.urls")),
    path("bibliometria/", include("bibliometria.urls")),
]

admin.site.site_header = "FRR · Framework de Rentabilidad Regenerativa"
admin.site.site_title = "FRR"
admin.site.index_title = "Administración de datos de la investigación"
