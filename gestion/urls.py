# gestion/urls.py
from django.urls import path
from . import views

app_name = "gestion"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("annee/choisir/", views.annee_select, name="annee_select"),
    path("annee/choisir/<int:pk>/", views.annee_set_session, name="annee_set_session"),
    path("annee/choisir/create/", views.annee_create_and_select, name="annee_create_and_select"),

    # Référentiels
    path("annees/", views.annee_list, name="annee_list"),
    path("annees/create/", views.annee_create, name="annee_create"),
    path("annees/<int:pk>/activate/", views.annee_activate, name="annee_activate"),
    path("annees/<int:pk>/delete/", views.annee_delete, name="annee_delete"),

    path("niveaux/", views.niveau_list, name="niveau_list"),
    path("niveaux/create/", views.niveau_create, name="niveau_create"),
    path("niveaux/<int:pk>/update/", views.niveau_update, name="niveau_update"),
    path("niveaux/<int:pk>/delete/", views.niveau_delete, name="niveau_delete"),

    path("departements/", views.departement_list, name="departement_list"),
    path("departements/create/", views.departement_create, name="departement_create"),
    path("departements/<int:pk>/update/", views.departement_update, name="departement_update"),
    path("departements/<int:pk>/delete/", views.departement_delete, name="departement_delete"),


    path("salles/", views.salle_list, name="salle_list"),
    path("salles/create/", views.salle_create, name="salle_create"),
    path("salles/<int:pk>/update/", views.salle_update, name="salle_update"),
    path("salles/<int:pk>/delete/", views.salle_delete, name="salle_delete"),


    path("roles/", views.role_list, name="role_list"),
    path("roles/create/", views.role_create, name="role_create"),
    path("roles/<int:pk>/delete/", views.role_delete, name="role_delete"),
    path("roles/<int:pk>/update/", views.role_update, name="role_update"),


    path("responsables/", views.responsable_list, name="responsable_list"),
    path("responsables/create/", views.responsable_create, name="responsable_create"),
    path("responsables/<int:pk>/update/", views.responsable_update, name="responsable_update"),
    path("responsables/<int:pk>/toggle-admin/", views.responsable_toggle_admin, name="responsable_toggle_admin"),
    path("responsables/<int:pk>/delete/", views.responsable_delete, name="responsable_delete"),



    # Étudiants
    path("etudiants/", views.etudiant_list, name="etudiant_list"),
    path("etudiants/create/", views.etudiant_create, name="etudiant_create"),
    path("etudiants/<int:pk>/update/", views.etudiant_update, name="etudiant_update"),
    path("etudiants/<int:pk>/delete/", views.etudiant_delete, name="etudiant_delete"),


    # Métier (placeholders pour éviter Reverse error)
    path("memoires/", views.memoire_list, name="memoire_list"),
    path("memoires/create/", views.memoire_create, name="memoire_create"),
    path("memoires/<int:pk>/update/", views.memoire_update, name="memoire_update"),
    path("memoires/<int:pk>/delete/", views.memoire_delete, name="memoire_delete"),

    path("soutenances/", views.soutenance_list, name="soutenance_list"),



    # Encadrements
    path("encadrements/", views.encadrement_list, name="encadrement_list"),
    path("encadrements/create/", views.encadrement_create, name="encadrement_create"),
    path(
        "encadrements/<int:id_responsable>/<int:id_memoire>/update/",
        views.encadrement_update,
        name="encadrement_update",
    ),
    path(
        "encadrements/<int:id_responsable>/<int:id_memoire>/delete/",
        views.encadrement_delete,
        name="encadrement_delete",
    ),

]
