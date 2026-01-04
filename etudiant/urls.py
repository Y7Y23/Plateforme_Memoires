from django.urls import path
from . import views

app_name = "etudiant"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("memoires/", views.memoire_list, name="memoire_list"),
    path("memoires/create/", views.memoire_create, name="memoire_create"),
    path("memoires/<int:id_memoire>/", views.memoire_detail, name="memoire_detail"),
]