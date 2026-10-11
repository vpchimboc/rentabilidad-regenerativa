from django.urls import path

from bibliometria import views

urlpatterns = [
    path("", views.matriz, name="bibliometria_matriz"),
]
