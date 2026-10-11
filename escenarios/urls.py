from django.urls import path

from escenarios import views

urlpatterns = [
    path("", views.lista, name="escenario_lista"),
    path("periodo/<int:pk>/", views.simular_periodo, name="escenario_simular"),
]
