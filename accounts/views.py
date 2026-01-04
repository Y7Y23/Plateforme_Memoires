from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .utils import get_active_annee
from .forms import LoginForm
from .decorators import isms_login_required


def home(request):
    if request.user.is_authenticated:
        return redirect("accounts:post_login")
    return redirect("accounts:login")


def login_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:post_login")

    form = LoginForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        mot_de_pass = form.cleaned_data["mot_de_pass"]

        user = authenticate(request, username=email, password=mot_de_pass)
        if user is None:
            messages.error(request, "Email ou mot de passe incorrect.")
            return render(request, "accounts/login.html", {"form": form})

        login(request, user)

        # ✅ sécurité : backend doit définir actor_type
        actor = request.session.get("actor_type")
        if actor not in ("responsable", "etudiant"):
            logout(request)
            request.session.flush()
            messages.error(request, "Session invalide. Reconnecte-toi.")
            return redirect("accounts:login")

        return redirect("accounts:post_login")

    return render(request, "accounts/login.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    request.session.flush()
    messages.info(request, "Déconnecté.")
    return redirect("accounts:login")


@isms_login_required
def post_login_redirect(request):
    """
    Routing central après login.

    - SUPERADMIN (responsable + is_admin=True) -> choisit année (gestion:annee_select)
    - Responsable normal / Étudiant -> année active auto (session annee_id/annee_libelle)
    """
    actor = request.session.get("actor_type")

    # --- SUPERADMIN ---
    if actor == "responsable" and request.session.get("is_admin"):
        if request.session.get("annee_id") is None:
            return redirect("gestion:annee_select")
        return redirect("gestion:dashboard")

    # --- RESPONSABLE normal / ETUDIANT : année active auto ---
    if actor in ("responsable", "etudiant"):
        active = get_active_annee()
        if not active:
            messages.error(request, "Aucune année universitaire active. Contacte l’admin.")
            logout(request)
            request.session.flush()
            return redirect("accounts:login")

        request.session["annee_id"] = active["id_annee"]
        request.session["annee_libelle"] = active["libelle"]

        if actor == "responsable":
            return redirect("responsable:dashboard")
        return redirect("etudiant:dashboard")

    # --- fallback ---
    messages.error(request, "Session invalide. Reconnecte-toi.")
    logout(request)
    request.session.flush()
    return redirect("accounts:login")
