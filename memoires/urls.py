from django.urls import path
from . import views

app_name = "memoires"

urlpatterns = [
    path("", views.memoire_list, name="memoire_list"),

    # mémoires
    path("memoires/", views.memoire_list, name="memoire_list"),
    path("memoires/nouveau/", views.memoire_create, name="memoire_create"),
    path("memoires/<int:id_memoire>/", views.memoire_detail, name="memoire_detail"),

    # workflow (fonctions SQL)
    path("memoires/<int:id_memoire>/mettre-en-verification/", views.memoire_mettre_en_verification, name="memoire_mettre_en_verification"),
    path("memoires/<int:id_memoire>/valider/", views.memoire_valider, name="memoire_valider"),
    path("memoires/<int:id_memoire>/refuser/", views.memoire_refuser, name="memoire_refuser"),

    # soutenances + dashboard
    path("soutenances/a-venir/", views.soutenances_a_venir, name="soutenances_a_venir"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/refresh/", views.refresh_stats, name="refresh_stats"),
]
