from django.conf import settings
from django.db import connection, transaction
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST

from .models import Memoire
from .forms import MemoireCreateForm


def _call(sql: str, params: list | None = None, fetchone=False, fetchall=False):
    params = params or []
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            if fetchone:
                return cursor.fetchone()
            if fetchall:
                return cursor.fetchall()
    return None


# 1) LISTE (filtres + recherche)
def memoire_list(request):
    qs = Memoire.objects.all().order_by("-date_depot")

    q = request.GET.get("q", "").strip()
    statut = request.GET.get("statut", "").strip()
    id_annee = request.GET.get("id_annee", "").strip()

    if q:
        qs = qs.filter(titre__icontains=q)
    if statut:
        qs = qs.filter(statut=statut)
    if id_annee:
        qs = qs.filter(id_annee=id_annee)

    return render(request, "memoires/memoire_list.html", {
        "memoires": qs,
        "q": q,
        "statut": statut,
        "id_annee": id_annee,
        "statuts": ["DEPOSE","EN_VERIFICATION","VALIDE","REFUSE"],
    })


# 2) CRÉER / DÉPOSER (upload)
def memoire_create(request):
    if request.method == "POST":
        form = MemoireCreateForm(request.POST, request.FILES)
        if form.is_valid():
            d = form.cleaned_data

            fichier_path = None
            f = request.FILES.get("fichier_pdf")
            if f:
                # sauvegarde simple dans MEDIA_ROOT/memoires/
                import os
                from django.core.files.storage import FileSystemStorage

                fs = FileSystemStorage(location=settings.MEDIA_ROOT / "memoires")
                saved_name = fs.save(f.name, f)
                fichier_path = f"memoires/{saved_name}"  # chemin relatif MEDIA

            try:
                # INSERT direct (statut DEPOSE par défaut côté BD)
                _call("""
                    INSERT INTO isms.memoire(titre, type, description, fichier_pdf, id_etudiant, id_annee)
                    VALUES (%s,%s,%s,%s,%s,%s)
                """, [d["titre"], d["type"], d["description"], fichier_path, d["id_etudiant"], d["id_annee"]])

                messages.success(request, "Mémoire déposé avec succès.")
                return redirect("memoires:memoire_list")
            except Exception as e:
                messages.error(request, f"Erreur dépôt: {e}")
        else:
            messages.error(request, "Formulaire invalide.")
    else:
        form = MemoireCreateForm()

    return render(request, "memoires/memoire_create.html", {"form": form})


# 3) DÉTAIL
def memoire_detail(request, id_memoire: int):
    memoire = get_object_or_404(Memoire, pk=id_memoire)
    return render(request, "memoires/memoire_detail.html", {"memoire": memoire})


# 4) WORKFLOW (fonctions SQL existantes)
@require_POST
def memoire_mettre_en_verification(request, id_memoire: int):
    try:
        _call("SELECT isms.fn_mettre_en_verification(%s);", [id_memoire])
        messages.success(request, "Mémoire mis en vérification.")
    except Exception as e:
        messages.error(request, f"Erreur: {e}")
    return redirect("memoires:memoire_detail", id_memoire=id_memoire)


@require_POST
def memoire_valider(request, id_memoire: int):
    try:
        _call("SELECT isms.fn_valider_memoire(%s);", [id_memoire])
        messages.success(request, "Mémoire validé.")
    except Exception as e:
        messages.error(request, f"Erreur: {e}")
    return redirect("memoires:memoire_detail", id_memoire=id_memoire)


@require_POST
def memoire_refuser(request, id_memoire: int):
    motif = (request.POST.get("motif") or "").strip()
    try:
        _call("SELECT isms.fn_refuser_memoire(%s, %s);", [id_memoire, motif])
        messages.success(request, "Mémoire refusé (motif ajouté).")
    except Exception as e:
        messages.error(request, f"Erreur: {e}")
    return redirect("memoires:memoire_detail", id_memoire=id_memoire)


def soutenances_a_venir(request):
    rows = _call("""
        SELECT
            s.id_soutenance,
            (s.date_::timestamp + s.heure) AS datetime_soutenance,
            sa.nom_salle,
            j.nom_jury,
            m.titre AS memoire_titre,
            e.nom AS etudiant_nom,
            e.prenom AS etudiant_prenom,
            e.email AS etudiant_email,
            a.libelle AS annee_universitaire
        FROM soutenance s
        JOIN salle sa ON sa.id_salle = s.id_salle
        JOIN jury j ON j.id_jury = s.id_jury
        JOIN memoire m ON m.id_memoire = s.id_memoire
        JOIN etudiant e ON e.id_etudiant = m.id_etudiant
        JOIN annee_universitaire a ON a.id_annee = s.id_annee
        WHERE s.statut = 'PLANIFIEE'
          AND (s.date_::timestamp + s.heure) > NOW()
        ORDER BY datetime_soutenance;
    """, fetchall=True) or []

    soutenances = [{
        "id_soutenance": r[0],
        "datetime": r[1],
        "nom_salle": r[2],
        "nom_jury": r[3],
        "memoire_titre": r[4],
        "etudiant": f"{r[5]} {r[6]} ({r[7]})",
        "annee": r[8],
    } for r in rows]

    return render(request, "memoires/soutenances_a_venir.html", {"soutenances": soutenances})

# 6) DASHBOARD (MV)
def dashboard(request):
    rows = _call("""
        SELECT annee_universitaire, nom_departement,
               total_memoires, memoires_valides, memoires_refuses, memoires_en_verification, memoires_deposes
        FROM isms.mv_stats_departement
        ORDER BY annee_universitaire, nom_departement;
    """, fetchall=True) or []

    stats = [{
        "annee": r[0],
        "dept": r[1],
        "total": r[2],
        "valides": r[3],
        "refuses": r[4],
        "verif": r[5],
        "deposes": r[6],
    } for r in rows]

    return render(request, "memoires/dashboard.html", {"stats": stats})


@require_POST
def refresh_stats(request):
    try:
        _call("SELECT isms.fn_refresh_stats();")
        messages.success(request, "Stats rafraîchies.")
    except Exception as e:
        messages.error(request, f"Erreur refresh: {e}")
    return redirect("memoires:dashboard")
