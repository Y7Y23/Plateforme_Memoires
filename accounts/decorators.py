from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def isms_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")

        actor = request.session.get("actor_type")
        if actor not in ("responsable", "etudiant"):
            messages.error(request, "Session invalide. Reconnecte-toi.")
            return redirect("accounts:login")

        return view_func(request, *args, **kwargs)
    return wrapper


def superadmin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")

        if request.session.get("actor_type") != "responsable" or not request.session.get("is_admin"):
            messages.error(request, "Accès réservé au SuperAdmin.")
            return redirect("accounts:post_login")

        return view_func(request, *args, **kwargs)
    return wrapper


def responsable_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")

        if request.session.get("actor_type") != "responsable":
            messages.error(request, "Accès réservé aux responsables.")
            return redirect("accounts:post_login")

        return view_func(request, *args, **kwargs)
    return wrapper


def etudiant_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")

        if request.session.get("actor_type") != "etudiant":
            messages.error(request, "Accès réservé aux étudiants.")
            return redirect("accounts:post_login")

        return view_func(request, *args, **kwargs)
    return wrapper


def admin_year_required(view_func):
    """
    Règle:
    - SuperAdmin: doit choisir l'année manuellement => gestion:annee_select
    - Responsable normal / Etudiant: année active auto via accounts:post_login
      => si annee_id manque, on renvoie vers accounts:post_login
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.session.get("annee_id") is not None:
            return view_func(request, *args, **kwargs)

        actor = request.session.get("actor_type")

        # SuperAdmin -> choix année
        if actor == "responsable" and request.session.get("is_admin"):
            messages.info(request, "Choisis d’abord l’année universitaire.")
            return redirect("gestion:annee_select")

        # Responsable normal / Étudiant -> annee active auto
        messages.info(request, "Année universitaire non initialisée. Reconnexion automatique.")
        return redirect("accounts:post_login")

    return wrapper
