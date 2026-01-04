from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import connection, IntegrityError, DatabaseError
from django.views.decorators.http import require_POST

from accounts.decorators import etudiant_required, admin_year_required


def fetchall_dict(cur):
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def save_memoire_pdf(uploaded_file):
    """
    Reprend ta logique existante si tu as déjà une fonction similaire.
    Ici un placeholder: tu dois l’adapter selon ton projet (MEDIA_ROOT, dossier memoires, nom unique...).
    """
    from django.conf import settings
    import os
    from datetime import datetime

    folder = os.path.join(settings.MEDIA_ROOT, "memoires")
    os.makedirs(folder, exist_ok=True)

    safe_name = uploaded_file.name.replace(" ", "_")
    filename = datetime.now().strftime("%Y%m%d_%H%M%S_") + safe_name
    path = os.path.join(folder, filename)

    with open(path, "wb+") as f:
        for chunk in uploaded_file.chunks():
            f.write(chunk)

    # ✅ IMPORTANT: tu stockes déjà "memoires/xxx.pdf" (comme on a vu)
    return f"memoires/{filename}"


# =========================================================
# DASHBOARD ETUDIANT
# =========================================================
@etudiant_required
@admin_year_required
def dashboard(request):
    annee_id = request.session.get("annee_id")
    etudiant_id = request.session.get("etudiant_id")

    stats = {"total": 0, "attente": 0, "valides": 0, "refuses": 0}
    soutenance = None

    with connection.cursor() as cur:
        # Stats mémoires
        cur.execute("""
            SELECT COUNT(*)
            FROM isms.memoire
            WHERE id_annee=%s AND id_etudiant=%s
        """, [annee_id, etudiant_id])
        stats["total"] = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*)
            FROM isms.memoire
            WHERE id_annee=%s AND id_etudiant=%s
              AND statut IN ('DEPOSE','EN_VERIFICATION')
        """, [annee_id, etudiant_id])
        stats["attente"] = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*)
            FROM isms.memoire
            WHERE id_annee=%s AND id_etudiant=%s AND statut='VALIDE'
        """, [annee_id, etudiant_id])
        stats["valides"] = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*)
            FROM isms.memoire
            WHERE id_annee=%s AND id_etudiant=%s AND statut='REFUSE'
        """, [annee_id, etudiant_id])
        stats["refuses"] = cur.fetchone()[0]

        # Soutenance liée au mémoire (si existante)
        cur.execute("""
            SELECT
              s.id_soutenance, s.date_, s.heure, s.statut,
              sa.nom_salle,
              m.id_memoire, m.titre,
              j.nom_jury
            FROM isms.memoire m
            JOIN isms.soutenance s ON s.id_memoire = m.id_memoire
            JOIN isms.salle sa ON sa.id_salle = s.id_salle
            JOIN isms.jury j ON j.id_jury = s.id_jury
            WHERE m.id_annee=%s AND m.id_etudiant=%s
            ORDER BY s.date_ DESC, s.heure DESC
            LIMIT 1
        """, [annee_id, etudiant_id])
        r = cur.fetchone()

    if r:
        soutenance = {
            "id_soutenance": r[0],
            "date_": r[1],
            "heure": r[2],
            "statut": r[3],
            "nom_salle": r[4],
            "id_memoire": r[5],
            "titre": r[6],
            "nom_jury": r[7],
        }

    return render(request, "etudiants/dashboard.html", {
        "annee_libelle": request.session.get("annee_libelle"),
        "stats": stats,
        "soutenance": soutenance,
    })


# =========================================================
# LISTE MEMOIRES
# =========================================================
@etudiant_required
@admin_year_required
def memoire_list(request):
    annee_id = request.session.get("annee_id")
    etudiant_id = request.session.get("etudiant_id")

    q = (request.GET.get("q") or "").strip().lower()
    statut = (request.GET.get("statut") or "").strip()

    where = ["m.id_annee=%s", "m.id_etudiant=%s"]
    params = [annee_id, etudiant_id]

    if statut in ("DEPOSE", "EN_VERIFICATION", "VALIDE", "REFUSE"):
        where.append("m.statut=%s")
        params.append(statut)

    if q:
        like = f"%{q}%"
        where.append("LOWER(m.titre) LIKE %s")
        params.append(like)

    sql = f"""
        SELECT m.id_memoire, m.titre, m.type, m.statut, m.date_depot, m.fichier_pdf
        FROM isms.memoire m
        WHERE {" AND ".join(where)}
        ORDER BY m.date_depot DESC
    """

    with connection.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    memoires = [{
        "id_memoire": r[0],
        "titre": r[1],
        "type": r[2],
        "statut": r[3],
        "date_depot": r[4],
        "fichier_pdf": r[5],
    } for r in rows]

    return render(request, "etudiants/memoires/list.html", {
        "memoires": memoires,
        "q": q,
        "statut": statut,
        "STATUTS": ["DEPOSE", "EN_VERIFICATION", "VALIDE", "REFUSE"],
    })


# =========================================================
# CREER MEMOIRE (DEPOT)
# =========================================================
@etudiant_required
@admin_year_required
def memoire_create(request):
    annee_id = request.session.get("annee_id")
    etudiant_id = request.session.get("etudiant_id")

    types = ["PFE", "MEMOIRE", "RAPPORT", "THESE"]

    if request.method == "POST":
        titre = (request.POST.get("titre") or "").strip()
        type_ = (request.POST.get("type") or "").strip()
        description = (request.POST.get("description") or "").strip()

        pdf = request.FILES.get("fichier_pdf")

        if not titre or not type_ or type_ not in types:
            messages.error(request, "Titre et type sont obligatoires.")
            return render(request, "etudiants/memoires/form.html", {"types": types, "data": request.POST})

        if not pdf:
            messages.error(request, "Le fichier PDF est obligatoire.")
            return render(request, "etudiants/memoires/form.html", {"types": types, "data": request.POST})

        try:
            fichier_pdf = save_memoire_pdf(pdf)

            with connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO isms.memoire(titre, type, description, fichier_pdf, statut, id_etudiant, id_annee)
                    VALUES (%s, %s, %s, %s, 'DEPOSE', %s, %s)
                """, [titre, type_, description or None, fichier_pdf, etudiant_id, annee_id])

            messages.success(request, "Mémoire déposé avec succès.")
            return redirect("etudiant:memoire_list")

        except DatabaseError:
            messages.error(request, "Erreur base de données lors du dépôt.")
            return render(request, "etudiants/memoires/form.html", {"types": types, "data": request.POST})

    return render(request, "etudiants/memoires/form.html", {"types": types, "data": {}})


# =========================================================
# DETAIL MEMOIRE
# =========================================================
@etudiant_required
@admin_year_required
def memoire_detail(request, id_memoire: int):
    annee_id = request.session.get("annee_id")
    etudiant_id = request.session.get("etudiant_id")

    with connection.cursor() as cur:
        cur.execute("""
            SELECT id_memoire, titre, type, description, fichier_pdf, date_depot, statut
            FROM isms.memoire
            WHERE id_memoire=%s AND id_annee=%s AND id_etudiant=%s
            LIMIT 1
        """, [id_memoire, annee_id, etudiant_id])
        r = cur.fetchone()

        if not r:
            messages.error(request, "Mémoire introuvable ou accès non autorisé.")
            return redirect("etudiant:memoire_list")

        cur.execute("""
            SELECT r2.nom, r2.prenom, r2.email, en.encadrement
            FROM isms.encadrement en
            JOIN isms.responsable r2 ON r2.id_responsable = en.id_responsable
            WHERE en.id_memoire=%s
            ORDER BY en.encadrement, r2.nom, r2.prenom
        """, [id_memoire])
        encadreurs = fetchall_dict(cur)

        # Soutenance si elle existe
        cur.execute("""
            SELECT
              s.id_soutenance, s.date_, s.heure, s.statut,
              sa.nom_salle,
              j.nom_jury
            FROM isms.soutenance s
            JOIN isms.salle sa ON sa.id_salle = s.id_salle
            JOIN isms.jury j ON j.id_jury = s.id_jury
            WHERE s.id_memoire=%s AND s.id_annee=%s
            LIMIT 1
        """, [id_memoire, annee_id])
        s = cur.fetchone()

    mem = {
        "id_memoire": r[0],
        "titre": r[1],
        "type": r[2],
        "description": r[3],
        "fichier_pdf": r[4],     # stocké "memoires/xxx.pdf"
        "date_depot": r[5],
        "statut": r[6],
    }

    soutenance = None
    if s:
        soutenance = {
            "id_soutenance": s[0],
            "date_": s[1],
            "heure": s[2],
            "statut": s[3],
            "nom_salle": s[4],
            "nom_jury": s[5],
        }

    return render(request, "etudiants/memoires/detail.html", {
        "mem": mem,
        "encadreurs": encadreurs,
        "soutenance": soutenance,
    })
