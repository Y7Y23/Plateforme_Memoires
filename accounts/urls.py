from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("", views.home, name="home"),                 # redirige vers login ou dashboard
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    path("go/", views.post_login_redirect, name="post_login"),

    path("dashboard/superadmin/", views.dashboard_superadmin, name="dashboard_superadmin"),
    path("dashboard/responsable/", views.dashboard_responsable, name="dashboard_responsable"),
    path("dashboard/etudiant/", views.dashboard_etudiant, name="dashboard_etudiant"),
]
