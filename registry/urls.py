from django.urls import path
from . import views

app_name = "registry"

urlpatterns = [
    path("", views.home, name="home"),
    path("create/", views.create_record, name="create_record"),
]
