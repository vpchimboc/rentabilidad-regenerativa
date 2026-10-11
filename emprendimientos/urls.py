from django.urls import path

from emprendimientos import views

urlpatterns = [
    path("", views.lista, name="emprendimiento_lista"),
    path("exportar/", views.exportar, name="emprendimiento_exportar"),
    path("<int:pk>/", views.detalle, name="emprendimiento_detalle"),
    path("periodo/<int:pk>/evaluar/", views.evaluar_periodo, name="evaluar_periodo"),
]
