from django.contrib import messages
from django.db import connection
from django.shortcuts import redirect, render
from accounts.decorators import superadmin_required, admin_year_required
import os 
from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone

# ---------- HELPERS ----------
def fetchall_dict(cur):
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


# ---------- DASHBOARD ----------
@superadmin_required
def dashboard(request):
    with connection.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM isms.etudiant;")
        nb_etudiants = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM isms.responsable;")
        nb_responsables = cur.fetchone()[0]
        cur.execute("SELECT statut, COUNT(*) FROM isms.memoire GROUP BY statut ORDER BY statut;")
        mem_stats = cur.fetchall()

    return render(request, "gestion/dashboard.html", {
        "nb_etudiants": nb_etudiants,
        "nb_responsables": nb_responsables,
        "mem_stats": mem_stats,
    })


# =========================
# REFERENTIELS
# =========================

# ---- ANNEE UNIVERSITAIRE ----

@superadmin_required
def annee_select(request):
    """Liste des années + choix (stocké en session)."""
    with connection.cursor() as cur:
        cur.execute("""
            SELECT id_annee, libelle, active
            FROM isms.annee_universitaire
            ORDER BY id_annee DESC;
        """)
        rows = fetchall_dict(cur)

    return render(request, "gestion/annee_select.html", {"rows": rows})


@superadmin_required
def annee_set_session(request, pk):
    """Sélectionner une année : on la met en session (et optionnellement active en DB)."""
    with connection.cursor() as cur:
        cur.execute("SELECT libelle FROM isms.annee_universitaire WHERE id_annee=%s;", [pk])
        row = cur.fetchone()

    if not row:
        messages.error(request, "Année introuvable.")
        return redirect("gestion:annee_select")

    libelle = row[0]
    request.session["annee_id"] = int(pk)
    request.session["annee_libelle"] = libelle

    # OPTION (recommandée) : rendre l'année active globalement
    with connection.cursor() as cur:
        cur.execute("UPDATE isms.annee_universitaire SET active = FALSE;")
        cur.execute("UPDATE isms.annee_universitaire SET active = TRUE WHERE id_annee=%s;", [pk])

    messages.success(request, f"Année sélectionnée : {libelle}")
    return redirect("gestion:dashboard")


@superadmin_required
def annee_create_and_select(request):
    """Créer une année + la sélectionner immédiatement."""
    if request.method != "POST":
        return redirect("gestion:annee_select")

    libelle = (request.POST.get("libelle") or "").strip()
    if not libelle:
        messages.error(request, "Libellé obligatoire.")
        return redirect("gestion:annee_select")

    with connection.cursor() as cur:
        cur.execute("""
            INSERT INTO isms.annee_universitaire(libelle, active)
            VALUES (%s, TRUE)
            RETURNING id_annee;
        """, [libelle])
        new_id = cur.fetchone()[0]

        # garantir une seule active
        cur.execute("UPDATE isms.annee_universitaire SET active = FALSE WHERE id_annee <> %s;", [new_id])

    request.session["annee_id"] = int(new_id)
    request.session["annee_libelle"] = libelle

    messages.success(request, f"Année créée et sélectionnée : {libelle}")
    return redirect("gestion:dashboard")


@superadmin_required
def annee_list(request):
    with connection.cursor() as cur:
        cur.execute("SELECT id_annee, libelle, active FROM isms.annee_universitaire ORDER BY id_annee DESC;")
        rows = fetchall_dict(cur)
    return render(request, "gestion/annees/list.html", {"rows": rows})


@superadmin_required
def annee_create(request):
    if request.method == "POST":
        libelle = (request.POST.get("libelle") or "").strip()
        if not libelle:
            messages.error(request, "Libellé obligatoire.")
            return redirect("gestion:annee_list")

        with connection.cursor() as cur:
            cur.execute("INSERT INTO isms.annee_universitaire(libelle, active) VALUES (%s, FALSE);", [libelle])

        messages.success(request, "Année ajoutée.")
        return redirect("gestion:annee_list")

    return render(request, "gestion/annees/create.html")


@superadmin_required
def annee_activate(request, pk):
    # une seule active (index unique partiel)
    with connection.cursor() as cur:
        cur.execute("UPDATE isms.annee_universitaire SET active = FALSE;")
        cur.execute("UPDATE isms.annee_universitaire SET active = TRUE WHERE id_annee = %s;", [pk])
    messages.success(request, "Année activée.")
    return redirect("gestion:annee_list")


@superadmin_required
def annee_delete(request, pk):
    with connection.cursor() as cur:
        cur.execute("DELETE FROM isms.annee_universitaire WHERE id_annee = %s;", [pk])
    messages.success(request, "Année supprimée.")
    return redirect("gestion:annee_list")


# ---- NIVEAU ----
@superadmin_required
def niveau_list(request):
    with connection.cursor() as cur:
        cur.execute("SELECT id_niveau, libelle FROM isms.niveau ORDER BY libelle;")
        rows = fetchall_dict(cur)
    return render(request, "gestion/niveaux/list.html", {"rows": rows})


@superadmin_required
def niveau_create(request):
    if request.method == "POST":
        libelle = (request.POST.get("libelle") or "").strip()
        if not libelle:
            messages.error(request, "Libellé obligatoire.")
            return redirect("gestion:niveau_list")
        with connection.cursor() as cur:
            cur.execute("INSERT INTO isms.niveau(libelle) VALUES (%s);", [libelle])
        messages.success(request, "Niveau ajouté.")
        return redirect("gestion:niveau_list")

    return render(request, "gestion/niveaux/create.html")

@superadmin_required
def niveau_update(request, pk):
    with connection.cursor() as cur:
        cur.execute("SELECT id_niveau, libelle FROM isms.niveau WHERE id_niveau=%s;", [pk])
        row = cur.fetchone()

    if not row:
        messages.error(request, "Niveau introuvable.")
        return redirect("gestion:niveau_list")

    niveau = {"id_niveau": row[0], "libelle": row[1]}

    if request.method == "POST":
        libelle = (request.POST.get("libelle") or "").strip()
        if not libelle:
            messages.error(request, "Libellé obligatoire.")
            return redirect("gestion:niveau_update", pk=pk)

        with connection.cursor() as cur:
            cur.execute("UPDATE isms.niveau SET libelle=%s WHERE id_niveau=%s;", [libelle, pk])

        messages.success(request, "Niveau modifié.")
        return redirect("gestion:niveau_list")

    return render(request, "gestion/niveaux/update.html", {"niveau": niveau})

from django.db import IntegrityError

@superadmin_required
def niveau_delete(request, pk):
    try:
        with connection.cursor() as cur:
            cur.execute("DELETE FROM isms.niveau WHERE id_niveau = %s;", [pk])
        messages.success(request, "Niveau supprimé.")
    except IntegrityError:
        messages.error(request, "Impossible de supprimer : ce niveau est lié à d'autres données (ex: départements).")
    return redirect("gestion:niveau_list")


# ---- DEPARTEMENT ----@superadmin_required
def departement_list(request):
    with connection.cursor() as cur:
        cur.execute("""
            SELECT d.id_departement, d.nom_departement, d.id_niveau, n.libelle AS niveau
            FROM isms.departement d
            JOIN isms.niveau n ON n.id_niveau = d.id_niveau
            ORDER BY d.nom_departement;
        """)
        rows = fetchall_dict(cur)

        cur.execute("SELECT id_niveau, libelle FROM isms.niveau ORDER BY libelle;")
        niveaux = fetchall_dict(cur)

    return render(request, "gestion/departements/list.html", {
        "rows": rows,
        "niveaux": niveaux
    })


@superadmin_required
def departement_create(request):
    if request.method == "POST":
        nom = (request.POST.get("nom_departement") or "").strip()
        id_niveau = request.POST.get("id_niveau")
        if not nom or not id_niveau:
            messages.error(request, "Nom + niveau obligatoires.")
            return redirect("gestion:departement_list")

        with connection.cursor() as cur:
            cur.execute(
                "INSERT INTO isms.departement(nom_departement, id_niveau) VALUES (%s, %s);",
                [nom, id_niveau],
            )
        messages.success(request, "Département ajouté.")
        return redirect("gestion:departement_list")

    return redirect("gestion:departement_list")


from django.db import IntegrityError

@superadmin_required
def departement_delete(request, pk):
    try:
        with connection.cursor() as cur:
            cur.execute("DELETE FROM isms.departement WHERE id_departement = %s;", [pk])
        messages.success(request, "Département supprimé.")
    except IntegrityError:
        # lié à d'autres tables (ex: etudiant, memoire, etc.)
        messages.error(request, "Impossible de supprimer : ce département est lié à d'autres données.")
    return redirect("gestion:departement_list")

@superadmin_required
def departement_update(request, pk):
    with connection.cursor() as cur:
        # charger departement
        cur.execute("""
            SELECT id_departement, nom_departement, id_niveau
            FROM isms.departement
            WHERE id_departement = %s;
        """, [pk])
        dep = cur.fetchone()

        # charger niveaux
        cur.execute("SELECT id_niveau, libelle FROM isms.niveau ORDER BY libelle;")
        niveaux = fetchall_dict(cur)

    if not dep:
        messages.error(request, "Département introuvable.")
        return redirect("gestion:departement_list")

    dep_data = {
        "id_departement": dep[0],
        "nom_departement": dep[1],
        "id_niveau": dep[2],
    }

    if request.method == "POST":
        nom = (request.POST.get("nom_departement") or "").strip()
        id_niveau = request.POST.get("id_niveau")

        if not nom or not id_niveau:
            messages.error(request, "Nom + niveau obligatoires.")
            return redirect("gestion:departement_update", pk=pk)

        with connection.cursor() as cur:
            cur.execute("""
                UPDATE isms.departement
                SET nom_departement=%s, id_niveau=%s
                WHERE id_departement=%s;
            """, [nom, id_niveau, pk])

        messages.success(request, "Département modifié.")
        return redirect("gestion:departement_list")

    return render(request, "gestion/departements/update.html", {
        "dep": dep_data,
        "niveaux": niveaux
    })


# ---- SALLE ----
@superadmin_required
def salle_list(request):
    with connection.cursor() as cur:
        cur.execute("SELECT id_salle, nom_salle FROM isms.salle ORDER BY nom_salle;")
        rows = fetchall_dict(cur)
    return render(request, "gestion/salles/list.html", {"rows": rows})



@superadmin_required
def salle_create(request):
    if request.method == "POST":
        nom = (request.POST.get("nom_salle") or "").strip()
        if not nom:
            messages.error(request, "Nom obligatoire.")
            return redirect("gestion:salle_list")
        with connection.cursor() as cur:
            cur.execute("INSERT INTO isms.salle(nom_salle) VALUES (%s);", [nom])
        messages.success(request, "Salle ajoutée.")
        return redirect("gestion:salle_list")
    return render(request, "gestion/salles/create.html")

@superadmin_required
def salle_update(request, pk):
    with connection.cursor() as cur:
        cur.execute("SELECT id_salle, nom_salle FROM isms.salle WHERE id_salle=%s;", [pk])
        row = cur.fetchone()

    if not row:
        messages.error(request, "Salle introuvable.")
        return redirect("gestion:salle_list")

    salle = {"id_salle": row[0], "nom_salle": row[1]}

    if request.method == "POST":
        nom = (request.POST.get("nom_salle") or "").strip()
        if not nom:
            messages.error(request, "Nom obligatoire.")
            return redirect("gestion:salle_update", pk=pk)

        with connection.cursor() as cur:
            cur.execute("UPDATE isms.salle SET nom_salle=%s WHERE id_salle=%s;", [nom, pk])

        messages.success(request, "Salle modifiée.")
        return redirect("gestion:salle_list")

    return render(request, "gestion/salles/update.html", {"salle": salle})


from django.db import IntegrityError

@superadmin_required
def salle_delete(request, pk):
    try:
        with connection.cursor() as cur:
            cur.execute("DELETE FROM isms.salle WHERE id_salle = %s;", [pk])
        messages.success(request, "Salle supprimée.")
    except IntegrityError:
        messages.error(request, "Impossible de supprimer : cette salle est liée à d'autres données (ex: soutenances).")
    return redirect("gestion:salle_list")


# ---- ROLE ----
@superadmin_required
def role_list(request):
    with connection.cursor() as cur:
        cur.execute("SELECT id_role, code, libelle FROM isms.role ORDER BY code;")
        rows = fetchall_dict(cur)
    return render(request, "gestion/roles/list.html", {"rows": rows})


@superadmin_required
def role_create(request):
    if request.method == "POST":
        code = (request.POST.get("code") or "").strip().upper()
        libelle = (request.POST.get("libelle") or "").strip()
        if not code or not libelle:
            messages.error(request, "Code + libellé obligatoires.")
            return redirect("gestion:role_list")
        with connection.cursor() as cur:
            cur.execute("INSERT INTO isms.role(code, libelle) VALUES (%s, %s);", [code, libelle])
        messages.success(request, "Rôle ajouté.")
        return redirect("gestion:role_list")
    return render(request, "gestion/roles/create.html")

@superadmin_required
def role_update(request, pk):
    with connection.cursor() as cur:
        cur.execute("SELECT id_role, code, libelle FROM isms.role WHERE id_role=%s;", [pk])
        row = cur.fetchone()

    if not row:
        messages.error(request, "Rôle introuvable.")
        return redirect("gestion:role_list")

    role = {"id_role": row[0], "code": row[1], "libelle": row[2]}

    if request.method == "POST":
        code = (request.POST.get("code") or "").strip().upper()
        libelle = (request.POST.get("libelle") or "").strip()

        if not code or not libelle:
            messages.error(request, "Code + libellé obligatoires.")
            return redirect("gestion:role_update", pk=pk)

        with connection.cursor() as cur:
            cur.execute("""
                UPDATE isms.role
                SET code=%s, libelle=%s
                WHERE id_role=%s;
            """, [code, libelle, pk])

        messages.success(request, "Rôle modifié.")
        return redirect("gestion:role_list")

    return render(request, "gestion/roles/update.html", {"role": role})

@superadmin_required
def role_delete(request, pk):
    try:
        with connection.cursor() as cur:
            cur.execute("DELETE FROM isms.role WHERE id_role = %s;", [pk])
        messages.success(request, "Rôle supprimé.")
    except IntegrityError:
        messages.error(request, "Impossible de supprimer : ce rôle est utilisé (ex: responsables).")
    return redirect("gestion:role_list")


@superadmin_required
def role_delete(request, pk):
    with connection.cursor() as cur:
        cur.execute("DELETE FROM isms.role WHERE id_role = %s;", [pk])
    messages.success(request, "Rôle supprimé.")
    return redirect("gestion:role_list")


# =========================
# UTILISATEURS: RESPONSABLE
# =========================
@superadmin_required
def responsable_list(request):
    with connection.cursor() as cur:
        cur.execute("""
            SELECT r.id_responsable, r.nom, r.prenom, r.email, r.is_admin, ro.code AS role_code
            FROM isms.responsable r
            JOIN isms.role ro ON ro.id_role = r.id_role
            ORDER BY r.id_responsable DESC;
        """)
        rows = fetchall_dict(cur)

        cur.execute("SELECT id_role, code FROM isms.role ORDER BY code;")
        roles = fetchall_dict(cur)

    return render(request, "gestion/responsables/list.html", {"rows": rows, "roles": roles})


@superadmin_required
def responsable_create(request):
    if request.method == "POST":
        nom = (request.POST.get("nom") or "").strip()
        prenom = (request.POST.get("prenom") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()
        mot_de_pass = (request.POST.get("mot_de_pass") or "").strip()
        id_role = request.POST.get("id_role")
        is_admin = True if request.POST.get("is_admin") == "on" else False

        if not (nom and prenom and email and mot_de_pass and id_role):
            messages.error(request, "Tous les champs sont obligatoires.")
            return redirect("gestion:responsable_list")

        with connection.cursor() as cur:
            cur.execute("""
                INSERT INTO isms.responsable(nom, prenom, email, mot_de_pass, id_role, is_admin)
                VALUES (%s,%s,%s,%s,%s,%s);
            """, [nom, prenom, email, mot_de_pass, id_role, is_admin])

        messages.success(request, "Responsable créé.")
        return redirect("gestion:responsable_list")

    return redirect("gestion:responsable_list")

@superadmin_required
def responsable_update(request, pk):
    with connection.cursor() as cur:
        # responsable
        cur.execute("""
            SELECT id_responsable, nom, prenom, email, is_admin, id_role
            FROM isms.responsable
            WHERE id_responsable=%s;
        """, [pk])
        row = cur.fetchone()

        # roles
        cur.execute("SELECT id_role, code FROM isms.role ORDER BY code;")
        roles = fetchall_dict(cur)

    if not row:
        messages.error(request, "Responsable introuvable.")
        return redirect("gestion:responsable_list")

    resp = {
        "id_responsable": row[0],
        "nom": row[1],
        "prenom": row[2],
        "email": row[3],
        "is_admin": row[4],
        "id_role": row[5],
    }

    if request.method == "POST":
        nom = (request.POST.get("nom") or "").strip()
        prenom = (request.POST.get("prenom") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()
        id_role = request.POST.get("id_role")
        is_admin = True if request.POST.get("is_admin") == "on" else False

        new_pass = (request.POST.get("mot_de_pass") or "").strip()  # optionnel

        if not (nom and prenom and email and id_role):
            messages.error(request, "Nom, prénom, email, rôle obligatoires.")
            return redirect("gestion:responsable_update", pk=pk)

        with connection.cursor() as cur:
            if new_pass:
                cur.execute("""
                    UPDATE isms.responsable
                    SET nom=%s, prenom=%s, email=%s, id_role=%s, is_admin=%s, mot_de_pass=%s
                    WHERE id_responsable=%s;
                """, [nom, prenom, email, id_role, is_admin, new_pass, pk])
            else:
                cur.execute("""
                    UPDATE isms.responsable
                    SET nom=%s, prenom=%s, email=%s, id_role=%s, is_admin=%s
                    WHERE id_responsable=%s;
                """, [nom, prenom, email, id_role, is_admin, pk])

        messages.success(request, "Responsable modifié.")
        return redirect("gestion:responsable_list")

    return render(request, "gestion/responsables/update.html", {"resp": resp, "roles": roles})


@superadmin_required
def responsable_toggle_admin(request, pk):
    with connection.cursor() as cur:
        cur.execute("UPDATE isms.responsable SET is_admin = NOT is_admin WHERE id_responsable = %s;", [pk])
    messages.success(request, "Droit admin mis à jour.")
    return redirect("gestion:responsable_list")


@superadmin_required
def responsable_delete(request, pk):
    try:
        with connection.cursor() as cur:
            cur.execute("DELETE FROM isms.responsable WHERE id_responsable = %s;", [pk])
        messages.success(request, "Responsable supprimé.")
    except IntegrityError:
        messages.error(request, "Impossible de supprimer : ce responsable est lié à d'autres données (ex: encadrement/jury).")
    return redirect("gestion:responsable_list")




# =========================
# UTILISATEURS: ETUDIANT
# =========================
@superadmin_required
def etudiant_list(request):
    q = (request.GET.get("q") or "").strip()

    with connection.cursor() as cur:
        if q:
            like = f"%{q.lower()}%"
            cur.execute("""
                SELECT id_etudiant, nom, prenom, email
                FROM isms.etudiant
                WHERE LOWER(nom) LIKE %s OR LOWER(prenom) LIKE %s OR LOWER(email) LIKE %s
                ORDER BY id_etudiant DESC;
            """, [like, like, like])
        else:
            cur.execute("""
                SELECT id_etudiant, nom, prenom, email
                FROM isms.etudiant
                ORDER BY id_etudiant DESC;
            """)

        rows = fetchall_dict(cur)

    return render(request, "gestion/etudiants/list.html", {"rows": rows, "q": q})



@superadmin_required
def etudiant_create(request):
    if request.method == "POST":
        nom = (request.POST.get("nom") or "").strip()
        prenom = (request.POST.get("prenom") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()
        mot_de_pass = (request.POST.get("mot_de_pass") or "").strip()

        if not (nom and prenom and email and mot_de_pass):
            messages.error(request, "Tous les champs sont obligatoires.")
            return redirect("gestion:etudiant_list")

        with connection.cursor() as cur:
            cur.execute("""
                INSERT INTO isms.etudiant(nom, prenom, email, mot_de_pass)
                VALUES (%s,%s,%s,%s);
            """, [nom, prenom, email, mot_de_pass])

        messages.success(request, "Étudiant créé.")
        return redirect("gestion:etudiant_list")

    return redirect("gestion:etudiant_list")

@superadmin_required
def etudiant_update(request, pk):
    with connection.cursor() as cur:
        cur.execute("""
            SELECT id_etudiant, nom, prenom, email
            FROM isms.etudiant
            WHERE id_etudiant=%s;
        """, [pk])
        row = cur.fetchone()

    if not row:
        messages.error(request, "Étudiant introuvable.")
        return redirect("gestion:etudiant_list")

    etu = {"id_etudiant": row[0], "nom": row[1], "prenom": row[2], "email": row[3]}

    if request.method == "POST":
        nom = (request.POST.get("nom") or "").strip()
        prenom = (request.POST.get("prenom") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()
        mot_de_pass = (request.POST.get("mot_de_pass") or "").strip()  # optionnel

        if not (nom and prenom and email):
            messages.error(request, "Nom, prénom, email obligatoires.")
            return redirect("gestion:etudiant_update", pk=pk)

        with connection.cursor() as cur:
            if mot_de_pass:
                cur.execute("""
                    UPDATE isms.etudiant
                    SET nom=%s, prenom=%s, email=%s, mot_de_pass=%s
                    WHERE id_etudiant=%s;
                """, [nom, prenom, email, mot_de_pass, pk])
            else:
                cur.execute("""
                    UPDATE isms.etudiant
                    SET nom=%s, prenom=%s, email=%s
                    WHERE id_etudiant=%s;
                """, [nom, prenom, email, pk])

        messages.success(request, "Étudiant modifié.")
        return redirect("gestion:etudiant_list")

    return render(request, "gestion/etudiants/update.html", {"etu": etu})


@superadmin_required
def etudiant_delete(request, pk):
    try:
        with connection.cursor() as cur:
            cur.execute("DELETE FROM isms.etudiant WHERE id_etudiant=%s;", [pk])
        messages.success(request, "Étudiant supprimé.")
    except IntegrityError:
        messages.error(request, "Impossible de supprimer : étudiant lié à d'autres données (ex: mémoire, note...).")
    return redirect("gestion:etudiant_list")



# =========================
# METIER (PLACEHOLDERS)
# =========================
@superadmin_required
@admin_year_required
def memoire_list(request):
    annee_id = request.session.get("annee_id")

    q = (request.GET.get("q") or "").strip().lower()
    statut = (request.GET.get("statut") or "").strip()
    type_ = (request.GET.get("type") or "").strip()

    where = ["m.id_annee = %s"]
    params = [annee_id]

    if statut:
        where.append("m.statut = %s")
        params.append(statut)

    if type_:
        where.append("m.type = %s")
        params.append(type_)

    if q:
        like = f"%{q}%"
        where.append("""
          (LOWER(m.titre) LIKE %s
           OR LOWER(e.nom) LIKE %s
           OR LOWER(e.prenom) LIKE %s
           OR LOWER(e.email) LIKE %s)
        """)
        params.extend([like, like, like, like])

    where_sql = "WHERE " + " AND ".join(where)

    with connection.cursor() as cur:
        cur.execute(f"""
            SELECT
              m.id_memoire, m.titre, m.type, m.statut, m.date_depot, m.fichier_pdf,
              e.id_etudiant, e.nom, e.prenom, e.email
            FROM isms.memoire m
            JOIN isms.etudiant e ON e.id_etudiant = m.id_etudiant
            {where_sql}
            ORDER BY m.id_memoire DESC;
        """, params)
        rows = fetchall_dict(cur)

        # étudiants de l'année active uniquement
        cur.execute("""
            SELECT id_etudiant, nom, prenom, email
            FROM isms.etudiant
            WHERE id_annee = %s
            ORDER BY id_etudiant DESC;
        """, [annee_id])
        etudiants = fetchall_dict(cur)

    statuts = ["DEPOSE", "EN_VERIFICATION", "VALIDE", "REFUSE"]
    types = ["PFE", "MEMOIRE", "RAPPORT", "THESE"]

    return render(request, "gestion/memoires/list.html", {
        "rows": rows,
        "etudiants": etudiants,
        "statuts": statuts,
        "types": types,
        "q": request.GET.get("q", ""),
        "statut_filtre": statut,
        "type_filtre": type_,
    })

import os
from django.conf import settings
from django.utils import timezone

def save_memoire_pdf(file_obj):
    folder = os.path.join(settings.MEDIA_ROOT, "memoires")
    os.makedirs(folder, exist_ok=True)

    ts = timezone.now().strftime("%Y%m%d_%H%M%S")
    safe_name = file_obj.name.replace(" ", "_")
    filename = f"{ts}_{safe_name}"

    abs_path = os.path.join(folder, filename)

    with open(abs_path, "wb+") as f:
        for chunk in file_obj.chunks():
            f.write(chunk)

    # IMPORTANT: on stocke en DB un chemin avec "/" (pas "\")
    rel_path = f"memoires/{filename}"
    return rel_path


@superadmin_required
@admin_year_required
def memoire_create(request):
    if request.method != "POST":
        return redirect("gestion:memoire_list")

    annee_id = request.session.get("annee_id")

    titre = (request.POST.get("titre") or "").strip()
    type_ = (request.POST.get("type") or "").strip()
    description = (request.POST.get("description") or "").strip()
    statut = (request.POST.get("statut") or "DEPOSE").strip()
    id_etudiant = request.POST.get("id_etudiant")

    if not (titre and type_ and id_etudiant):
        messages.error(request, "Titre, type et étudiant obligatoires.")
        return redirect("gestion:memoire_list")

    fichier_pdf = None
    if request.FILES.get("fichier_pdf"):
        fichier_pdf = save_memoire_pdf(request.FILES["fichier_pdf"])

    with connection.cursor() as cur:
        cur.execute("""
            INSERT INTO isms.memoire(titre, type, description, fichier_pdf, statut, id_etudiant, id_annee)
            VALUES (%s,%s,%s,%s,%s,%s,%s);
        """, [titre, type_, description or None, fichier_pdf, statut, id_etudiant, annee_id])

    messages.success(request, "Mémoire ajouté.")
    return redirect("gestion:memoire_list")

@superadmin_required
@admin_year_required
def memoire_update(request, pk):
    annee_id = request.session.get("annee_id")

    with connection.cursor() as cur:
        cur.execute("""
            SELECT id_memoire, titre, type, description, fichier_pdf, statut, id_etudiant
            FROM isms.memoire
            WHERE id_memoire=%s AND id_annee=%s;
        """, [pk, annee_id])
        row = cur.fetchone()

        cur.execute("""
            SELECT id_etudiant, nom, prenom, email
            FROM isms.etudiant
            WHERE id_annee=%s
            ORDER BY id_etudiant DESC;
        """, [annee_id])
        etudiants = fetchall_dict(cur)

    if not row:
        messages.error(request, "Mémoire introuvable (ou pas dans l'année active).")
        return redirect("gestion:memoire_list")

    mem = {
        "id_memoire": row[0],
        "titre": row[1],
        "type": row[2],
        "description": row[3],
        "fichier_pdf": row[4],
        "statut": row[5],
        "id_etudiant": row[6],
    }

    statuts = ["DEPOSE", "EN_VERIFICATION", "VALIDE", "REFUSE"]
    types = ["PFE", "MEMOIRE", "RAPPORT", "THESE"]

    if request.method == "POST":
        titre = (request.POST.get("titre") or "").strip()
        type_ = (request.POST.get("type") or "").strip()
        description = (request.POST.get("description") or "").strip()
        statut = (request.POST.get("statut") or "").strip()
        id_etudiant = request.POST.get("id_etudiant")

        if not (titre and type_ and statut and id_etudiant):
            messages.error(request, "Tous les champs obligatoires doivent être remplis.")
            return redirect("gestion:memoire_update", pk=pk)

        set_parts = ["titre=%s", "type=%s", "description=%s", "statut=%s", "id_etudiant=%s"]
        params = [titre, type_, description or None, statut, id_etudiant]

        # nouveau PDF optionnel
        if request.FILES.get("fichier_pdf"):
            fichier_pdf = save_memoire_pdf(request.FILES["fichier_pdf"])
            set_parts.append("fichier_pdf=%s")
            params.append(fichier_pdf)

        params.extend([pk, annee_id])

        with connection.cursor() as cur:
            cur.execute(f"""
                UPDATE isms.memoire
                SET {", ".join(set_parts)}
                WHERE id_memoire=%s AND id_annee=%s;
            """, params)

        messages.success(request, "Mémoire modifié.")
        return redirect("gestion:memoire_list")

    return render(request, "gestion/memoires/update.html", {
        "mem": mem,
        "etudiants": etudiants,
        "statuts": statuts,
        "types": types,
    })


@superadmin_required
@admin_year_required
def memoire_delete(request, pk):
    annee_id = request.session.get("annee_id")
    try:
        with connection.cursor() as cur:
            cur.execute("DELETE FROM isms.memoire WHERE id_memoire=%s AND id_annee=%s;", [pk, annee_id])
        messages.success(request, "Mémoire supprimé.")
    except IntegrityError:
        messages.error(request, "Impossible de supprimer : mémoire lié à encadrement / soutenance / note.")
    return redirect("gestion:memoire_list")


@superadmin_required
def soutenance_list(request):
    messages.info(request, "Module Soutenances : bientôt (Phase 1B).")
    return render(request, "gestion/soutenances/list.html")

@superadmin_required
@admin_year_required
def encadrement_list(request):
    annee_id = request.session.get("annee_id")

    q = (request.GET.get("q") or "").strip().lower()
    enc_type = (request.GET.get("encadrement") or "").strip()  # ENCADRANT / CO_ENCADRANT

    where = ["m.id_annee = %s"]
    params = [annee_id]

    if enc_type:
        where.append("en.encadrement = %s")
        params.append(enc_type)

    if q:
        like = f"%{q}%"
        where.append("""
          (
            LOWER(m.titre) LIKE %s
            OR LOWER(r.nom) LIKE %s OR LOWER(r.prenom) LIKE %s OR LOWER(r.email) LIKE %s
            OR LOWER(e.nom) LIKE %s OR LOWER(e.prenom) LIKE %s OR LOWER(e.email) LIKE %s
            OR LOWER(d.nom_departement) LIKE %s
          )
        """)
        params.extend([like, like, like, like, like, like, like, like])

    where_sql = "WHERE " + " AND ".join(where)

    with connection.cursor() as cur:
        # LISTE encadrements (avec étudiant + mémoire + dept)
        cur.execute(f"""
            SELECT
              en.id_responsable, en.id_memoire, en.encadrement,

              r.nom AS r_nom, r.prenom AS r_prenom, r.email AS r_email,

              m.titre AS m_titre, m.statut AS m_statut, m.type AS m_type,

              e.id_etudiant, e.nom AS e_nom, e.prenom AS e_prenom, e.email AS e_email,
              d.nom_departement AS dep_nom
            FROM isms.encadrement en
            JOIN isms.responsable r ON r.id_responsable = en.id_responsable
            JOIN isms.memoire m ON m.id_memoire = en.id_memoire
            JOIN isms.etudiant e ON e.id_etudiant = m.id_etudiant
            JOIN isms.departement d ON d.id_departement = e.id_departement
            {where_sql}
            ORDER BY m.id_memoire DESC, en.encadrement;
        """, params)
        rows = fetchall_dict(cur)

        # MEMOIRES de l'année active
        cur.execute("""
            SELECT m.id_memoire, m.titre, m.statut, m.type,
                   e.nom AS e_nom, e.prenom AS e_prenom
            FROM isms.memoire m
            JOIN isms.etudiant e ON e.id_etudiant = m.id_etudiant
            WHERE m.id_annee = %s
            ORDER BY m.id_memoire DESC;
        """, [annee_id])
        memoires = fetchall_dict(cur)

        # RESPONSABLES
        cur.execute("""
            SELECT id_responsable, nom, prenom, email
            FROM isms.responsable
            ORDER BY id_responsable DESC;
        """)
        responsables = fetchall_dict(cur)

    enc_types = ["ENCADRANT", "CO_ENCADRANT"]

    return render(request, "gestion/encadrements/list.html", {
        "rows": rows,
        "memoires": memoires,
        "responsables": responsables,
        "enc_types": enc_types,
        "q": request.GET.get("q", ""),
        "enc_filtre": enc_type,
    })


@superadmin_required
@admin_year_required
def encadrement_create(request):
    if request.method != "POST":
        return redirect("gestion:encadrement_list")

    annee_id = request.session.get("annee_id")

    id_responsable = request.POST.get("id_responsable")
    id_memoire = request.POST.get("id_memoire")
    enc_type = (request.POST.get("encadrement") or "").strip()

    if not (id_responsable and id_memoire and enc_type):
        messages.error(request, "Responsable, mémoire et type d'encadrement obligatoires.")
        return redirect("gestion:encadrement_list")

    # sécurité : mémoire doit être dans l'année active
    with connection.cursor() as cur:
        cur.execute("SELECT 1 FROM isms.memoire WHERE id_memoire=%s AND id_annee=%s;", [id_memoire, annee_id])
        if cur.fetchone() is None:
            messages.error(request, "Mémoire invalide (pas dans l'année active).")
            return redirect("gestion:encadrement_list")

    # règle : un seul ENCADRANT principal par mémoire
    if enc_type == "ENCADRANT":
        with connection.cursor() as cur:
            cur.execute("""
                SELECT 1
                FROM isms.encadrement
                WHERE id_memoire=%s AND encadrement='ENCADRANT'
                LIMIT 1;
            """, [id_memoire])
            if cur.fetchone():
                messages.error(request, "Ce mémoire a déjà un encadrant principal.")
                return redirect("gestion:encadrement_list")

    try:
        with connection.cursor() as cur:
            cur.execute("""
                INSERT INTO isms.encadrement(id_responsable, id_memoire, encadrement)
                VALUES (%s,%s,%s);
            """, [id_responsable, id_memoire, enc_type])
        messages.success(request, "Encadrement ajouté.")
    except IntegrityError:
        messages.error(request, "Déjà existant : ce responsable est déjà lié à ce mémoire.")

    return redirect("gestion:encadrement_list")

    if request.method != "POST":
        return redirect("gestion:encadrement_list")

    annee_id = request.session.get("annee_id")

    id_responsable = request.POST.get("id_responsable")
    id_memoire = request.POST.get("id_memoire")
    enc_type = (request.POST.get("encadrement") or "").strip()

    if not (id_responsable and id_memoire and enc_type):
        messages.error(request, "Responsable, mémoire et type d'encadrement obligatoires.")
        return redirect("gestion:encadrement_list")

    # sécurité : le mémoire doit appartenir à l'année active
    with connection.cursor() as cur:
        cur.execute("SELECT 1 FROM isms.memoire WHERE id_memoire=%s AND id_annee=%s;", [id_memoire, annee_id])
        if cur.fetchone() is None:
            messages.error(request, "Mémoire invalide (pas dans l'année active).")
            return redirect("gestion:encadrement_list")

    try:
        with connection.cursor() as cur:
            cur.execute("""
                INSERT INTO isms.encadrement(id_responsable, id_memoire, encadrement)
                VALUES (%s,%s,%s);
            """, [id_responsable, id_memoire, enc_type])
        messages.success(request, "Encadrement ajouté.")
    except IntegrityError:
        messages.error(request, "Déjà existant : ce responsable est déjà lié à ce mémoire.")

    return redirect("gestion:encadrement_list")

@superadmin_required
@admin_year_required
def encadrement_update(request, id_responsable, id_memoire):
    annee_id = request.session.get("annee_id")

    enc_types = ["ENCADRANT", "CO_ENCADRANT"]

    with connection.cursor() as cur:
        # sécurité année (mémoire ancien doit appartenir à l'année active)
        cur.execute("SELECT 1 FROM isms.memoire WHERE id_memoire=%s AND id_annee=%s;", [id_memoire, annee_id])
        if cur.fetchone() is None:
            messages.error(request, "Action refusée (mémoire hors année active).")
            return redirect("gestion:encadrement_list")

        # ligne encadrement existante (old)
        cur.execute("""
            SELECT en.id_responsable, en.id_memoire, en.encadrement,
                   r.nom, r.prenom, r.email,
                   m.titre, m.statut, m.type,
                   e.nom, e.prenom, e.email
            FROM isms.encadrement en
            JOIN isms.responsable r ON r.id_responsable = en.id_responsable
            JOIN isms.memoire m ON m.id_memoire = en.id_memoire
            JOIN isms.etudiant e ON e.id_etudiant = m.id_etudiant
            WHERE en.id_responsable=%s AND en.id_memoire=%s;
        """, [id_responsable, id_memoire])
        row = cur.fetchone()

        # listes pour dropdowns
        cur.execute("""
            SELECT m.id_memoire, m.titre, m.statut, m.type,
                   e.nom AS e_nom, e.prenom AS e_prenom
            FROM isms.memoire m
            JOIN isms.etudiant e ON e.id_etudiant = m.id_etudiant
            WHERE m.id_annee=%s
            ORDER BY m.id_memoire DESC;
        """, [annee_id])
        memoires = fetchall_dict(cur)

        cur.execute("""
            SELECT id_responsable, nom, prenom, email
            FROM isms.responsable
            ORDER BY id_responsable DESC;
        """)
        responsables = fetchall_dict(cur)

    if not row:
        messages.error(request, "Encadrement introuvable.")
        return redirect("gestion:encadrement_list")

    # données actuelles (old)
    enc = {
        "old_id_responsable": row[0],
        "old_id_memoire": row[1],
        "old_encadrement": row[2],

        "r_nom": row[3], "r_prenom": row[4], "r_email": row[5],
        "m_titre": row[6], "m_statut": row[7], "m_type": row[8],
        "e_nom": row[9], "e_prenom": row[10], "e_email": row[11],
    }

    if request.method == "POST":
        new_id_responsable = request.POST.get("id_responsable")
        new_id_memoire = request.POST.get("id_memoire")
        new_enc_type = (request.POST.get("encadrement") or "").strip()

        if not (new_id_responsable and new_id_memoire and new_enc_type):
            messages.error(request, "Tous les champs sont obligatoires.")
            return redirect("gestion:encadrement_update", id_responsable=id_responsable, id_memoire=id_memoire)

        if new_enc_type not in enc_types:
            messages.error(request, "Type d'encadrement invalide.")
            return redirect("gestion:encadrement_update", id_responsable=id_responsable, id_memoire=id_memoire)

        # sécurité : mémoire choisi doit appartenir à l'année active
        with connection.cursor() as cur:
            cur.execute("SELECT 1 FROM isms.memoire WHERE id_memoire=%s AND id_annee=%s;", [new_id_memoire, annee_id])
            if cur.fetchone() is None:
                messages.error(request, "Mémoire invalide (pas dans l'année active).")
                return redirect("gestion:encadrement_update", id_responsable=id_responsable, id_memoire=id_memoire)

        # règle : un seul ENCADRANT principal par mémoire (nouveau mémoire)
        if new_enc_type == "ENCADRANT":
            with connection.cursor() as cur:
                cur.execute("""
                    SELECT 1
                    FROM isms.encadrement
                    WHERE id_memoire=%s AND encadrement='ENCADRANT'
                      AND NOT (id_responsable=%s AND id_memoire=%s)
                    LIMIT 1;
                """, [new_id_memoire, enc["old_id_responsable"], enc["old_id_memoire"]])
                if cur.fetchone():
                    messages.error(request, "Ce mémoire a déjà un encadrant principal.")
                    return redirect("gestion:encadrement_update", id_responsable=id_responsable, id_memoire=id_memoire)

        # UPDATE "complet" = delete old + insert new (transaction)
        try:
            with connection.cursor() as cur:
                cur.execute("BEGIN;")

                # supprimer l'ancienne ligne
                cur.execute("""
                    DELETE FROM isms.encadrement
                    WHERE id_responsable=%s AND id_memoire=%s;
                """, [enc["old_id_responsable"], enc["old_id_memoire"]])

                # insérer la nouvelle ligne
                cur.execute("""
                    INSERT INTO isms.encadrement(id_responsable, id_memoire, encadrement)
                    VALUES (%s,%s,%s);
                """, [new_id_responsable, new_id_memoire, new_enc_type])

                cur.execute("COMMIT;")

            messages.success(request, "Encadrement modifié (responsable/mémoire/type).")
            return redirect("gestion:encadrement_list")

        except IntegrityError:
            # doublon PK ou contrainte
            with connection.cursor() as cur:
                cur.execute("ROLLBACK;")
            messages.error(request, "Impossible : cet encadrement existe déjà (doublon).")
            return redirect("gestion:encadrement_update", id_responsable=id_responsable, id_memoire=id_memoire)

    return render(request, "gestion/encadrements/update.html", {
        "enc": enc,
        "enc_types": enc_types,
        "memoires": memoires,
        "responsables": responsables,
        "old_id_responsable": enc["old_id_responsable"],
        "old_id_memoire": enc["old_id_memoire"],
    })


@superadmin_required
@admin_year_required
def encadrement_delete(request, id_responsable, id_memoire):
    annee_id = request.session.get("annee_id")

    # sécurité année
    with connection.cursor() as cur:
        cur.execute("SELECT 1 FROM isms.memoire WHERE id_memoire=%s AND id_annee=%s;", [id_memoire, annee_id])
        if cur.fetchone() is None:
            messages.error(request, "Action refusée (mémoire hors année active).")
            return redirect("gestion:encadrement_list")

    with connection.cursor() as cur:
        cur.execute("""
            DELETE FROM isms.encadrement
            WHERE id_responsable=%s AND id_memoire=%s;
        """, [id_responsable, id_memoire])

    messages.success(request, "Encadrement supprimé.")
    return redirect("gestion:encadrement_list")



