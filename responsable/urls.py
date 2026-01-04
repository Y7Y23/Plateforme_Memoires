from django.urls import path
from . import views

app_name = "responsable"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    # ENCADRANT / CO-ENCADRANT (mêmes pages, décision interdite pour CO)
    path("memoires/", views.memoire_list, name="memoire_list"),
    path("memoires/<int:id_memoire>/", views.memoire_detail, name="memoire_detail"),
    path("memoires/<int:id_memoire>/decision/", views.memoire_decision, name="memoire_decision"),

    # MEMBRE_JURY
    path("mes-soutenances/", views.my_soutenances, name="my_soutenances"),
    path("mes-soutenances/<int:id_soutenance>/", views.my_soutenance_detail, name="my_soutenance_detail"),
    path("mes-soutenances/<int:id_soutenance>/note/", views.my_soutenance_note, name="my_soutenance_note"),
]



