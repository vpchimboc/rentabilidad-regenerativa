from django.urls import path

from delphi import views

urlpatterns = [
    path("", views.panel, name="delphi_panel"),
    path("ronda/<int:pk>/cuestionario/", views.cuestionario, name="delphi_cuestionario"),
    path("ronda/<int:pk>/resultado/", views.resultado, name="delphi_resultado"),
]
