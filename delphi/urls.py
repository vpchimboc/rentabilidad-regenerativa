from django.urls import path

from delphi import views

urlpatterns = [
    path("", views.panel, name="delphi_panel"),
    path("ronda/<int:pk>/cuestionario/", views.cuestionario, name="delphi_cuestionario"),
    path("ronda/<int:pk>/resultado/", views.resultado, name="delphi_resultado"),
    path("ronda/<int:pk>/reporte/", views.reporte, name="delphi_reporte"),
    path("ronda/<int:pk>/experto/<int:experto_pk>/reevaluar/", views.habilitar_reevaluacion, name="delphi_reevaluar"),
    path("ronda/<int:pk>/participar/", views.participar, name="delphi_participar"),
    path("ronda/<int:pk>/responder/", views.responder, name="delphi_responder"),
    path("informe/", views.informe_word, name="delphi_informe"),
    path("rondas/nueva/", views.ronda_nueva, name="delphi_ronda_nueva"),
    path("rondas/<int:pk>/editar/", views.ronda_editar, name="delphi_ronda_editar"),
    path("rondas/<int:pk>/eliminar/", views.ronda_eliminar, name="delphi_ronda_eliminar"),
    path("expertos/nuevo/", views.experto_nuevo, name="delphi_experto_nuevo"),
    path("expertos/<int:pk>/editar/", views.experto_editar, name="delphi_experto_editar"),
    path("expertos/<int:pk>/eliminar/", views.experto_eliminar, name="delphi_experto_eliminar"),
]
