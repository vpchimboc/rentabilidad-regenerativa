from django.urls import path

from delphi import views

urlpatterns = [
    path("", views.panel, name="delphi_panel"),
    path("ronda/<int:pk>/cuestionario/", views.cuestionario, name="delphi_cuestionario"),
    path("ronda/<int:pk>/resultado/", views.resultado, name="delphi_resultado"),
    path("ronda/<int:pk>/reporte/", views.reporte, name="delphi_reporte"),
    path("expertos/nuevo/", views.experto_nuevo, name="delphi_experto_nuevo"),
    path("expertos/<int:pk>/editar/", views.experto_editar, name="delphi_experto_editar"),
    path("expertos/<int:pk>/eliminar/", views.experto_eliminar, name="delphi_experto_eliminar"),
]
