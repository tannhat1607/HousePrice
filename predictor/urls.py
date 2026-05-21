from django.urls import path

from . import views


app_name = "predictor"

urlpatterns = [
    path("", views.index, name="index"),
    path("linear/", views.linear, name="linear"),
    path("analytics/", views.analytics, name="analytics"),
]
