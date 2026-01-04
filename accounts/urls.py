from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    # home
    path("", views.home, name="home"),

    # auth
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # redirection intelligente après login
    path("go/", views.post_login_redirect, name="post_login"),
]
