from django.urls import path

from framework import views

urlpatterns = [
    path("", views.matriz, name="framework_matriz"),
]
