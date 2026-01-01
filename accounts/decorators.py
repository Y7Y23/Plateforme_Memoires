from django.shortcuts import redirect
from django.contrib import messages

def isms_login_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if request.session.get("actor_type") not in ("responsable", "etudiant"):
            messages.error(request, "Session invalide. Reconnecte-toi.")
            return redirect("accounts:login")
        return view_func(request, *args, **kwargs)
    return wrapper


def superadmin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if request.session.get("actor_type") != "responsable" or not request.session.get("is_admin"):
            messages.error(request, "Accès réservé au SuperAdmin.")
            return redirect("accounts:post_login")
        return view_func(request, *args, **kwargs)
    return wrapper


def responsable_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if request.session.get("actor_type") != "responsable":
            messages.error(request, "Accès réservé aux responsables.")
            return redirect("accounts:post_login")
        return view_func(request, *args, **kwargs)
    return wrapper


def etudiant_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if request.session.get("actor_type") != "etudiant":
            messages.error(request, "Accès réservé aux étudiants.")
            return redirect("accounts:post_login")
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_year_required(view_func):
    def wrapper(request, *args, **kwargs):
        if request.session.get("annee_id") is None:
            messages.info(request, "Choisis d’abord l’année universitaire.")
            return redirect("superadmin:annee_select")
        return view_func(request, *args, **kwargs)
    return wrapper