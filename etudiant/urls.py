from django.urls import path
from . import views

app_name = "etudiant"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("memoires/", views.memoire_list, name="memoire_list"),
    path("memoires/create/", views.memoire_create, name="memoire_create"),
    path("memoires/<int:id_memoire>/", views.memoire_detail, name="memoire_detail"),

    path("archive/", views.archive_list, name="archive_list"),
    path("archive/<int:id_memoire>/", views.archive_detail, name="archive_detail"),

    path("messages/", views.messages_list, name="messages_list"),
    path("messages/<int:id_conversation>/", views.messages_detail, name="messages_detail"),
    path("messages/<int:id_conversation>/send/", views.messages_send, name="messages_send"),
    path("memoires/<int:id_memoire>/conversation/start/", views.conversation_start, name="conversation_start"),

    path("soutenances/", views.soutenance_list, name="soutenance_list"),
    path("soutenances/<int:id_soutenance>/", views.soutenance_detail, name="soutenance_detail"),

]

