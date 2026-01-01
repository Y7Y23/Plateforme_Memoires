from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render

from .forms import LoginForm
from .decorators import superadmin_required, responsable_required, etudiant_required, isms_login_required


def home(request):
    if request.user.is_authenticated:
        return redirect("accounts:post_login")
    return redirect("accounts:login")


def login_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:post_login")

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            mot_de_pass = form.cleaned_data["mot_de_pass"]

            user = authenticate(request, username=email, password=mot_de_pass)
            if user is not None:
                login(request, user)
                return redirect("accounts:post_login")
            messages.error(request, "Email ou mot de passe incorrect.")
    else:
        form = LoginForm()

    return render(request, "accounts/login.html", {"form": form})

from django.views.decorators.http import require_POST

@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "Déconnecté.")
    return redirect("accounts:login")


@isms_login_required
def post_login_redirect(request):
    actor = request.session.get("actor_type")

    if actor == "responsable":
        if request.session.get("is_admin"):
            if request.session.get("annee_id") is None:
                return redirect("gestion:annee_select")
            return redirect("gestion:dashboard")
        return redirect("responsable:dashboard")

    if actor == "etudiant":
        return redirect("etudiant:dashboard")

    return redirect("accounts:login")


@superadmin_required
def dashboard_superadmin(request):
    # pour l'instant: page simple + liens
    return render(request, "accounts/dashboard_superadmin.html")


@responsable_required
def dashboard_responsable(request):
    return render(request, "accounts/dashboard_responsable.html")


@etudiant_required
def dashboard_etudiant(request):
    return render(request, "accounts/dashboard_etudiant.html")
