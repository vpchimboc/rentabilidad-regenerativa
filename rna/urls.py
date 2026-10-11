from django.urls import path

from rna import views

urlpatterns = [
    path("", views.panel, name="rna_panel"),
    path("entrenar/", views.entrenar_modelo, name="rna_entrenar"),
    path("predecir/", views.predecir_vista, name="rna_predecir"),
]
