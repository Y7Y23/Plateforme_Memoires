from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import connection, IntegrityError, DatabaseError
from django.views.decorators.http import require_POST
from accounts.decorators import etudiant_required, admin_year_required

from django.conf import settings

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

############################### MESSAGERIE ##################################

@etudiant_required
@admin_year_required
def messages_list(request):
    """
    Liste des conversations de l'étudiant.
    """
    etudiant_id = request.session.get("etudiant_id")
    q = (request.GET.get("q") or "").strip().lower()

    where = ["c.id_etudiant = %s"]
    params = [etudiant_id]

    if q:
        like = f"%{q}%"
        where.append("(LOWER(r.nom) LIKE %s OR LOWER(r.prenom) LIKE %s OR LOWER(m.titre) LIKE %s)")
        params.extend([like, like, like])

    sql = f"""
      SELECT
        c.id_conversation,
        c.created_at,
        r.id_responsable, r.nom, r.prenom, r.email,
        m.id_memoire, m.titre,
        (
          SELECT mm.contenu
          FROM isms.message mm
          WHERE mm.id_conversation = c.id_conversation
          ORDER BY mm.created_at DESC
          LIMIT 1
        ) AS last_msg,
        (
          SELECT mm.created_at
          FROM isms.message mm
          WHERE mm.id_conversation = c.id_conversation
          ORDER BY mm.created_at DESC
          LIMIT 1
        ) AS last_at,
        (
          SELECT COUNT(*)
          FROM isms.message mm
          WHERE mm.id_conversation = c.id_conversation
            AND mm.sender_type = 'RESPONSABLE'
            AND mm.is_read = FALSE
        ) AS unread_count
      FROM isms.conversation c
      JOIN isms.responsable r ON r.id_responsable = c.id_responsable
      JOIN isms.memoire m ON m.id_memoire = c.id_memoire
      WHERE {" AND ".join(where)}
      ORDER BY last_at DESC NULLS LAST, c.created_at DESC
    """

    with connection.cursor() as cur:
        cur.execute(sql, params)
        conversations = fetchall_dict(cur)

    return render(request, "etudiants/messages/list.html", {
        "conversations": conversations,
        "q": request.GET.get("q", ""),
    })


@etudiant_required
@admin_year_required
def messages_detail(request, id_conversation: int):
    """
    Détail conversation + messages.
    Marque comme lus les messages du responsable.
    """
    etudiant_id = request.session.get("etudiant_id")

    with connection.cursor() as cur:
        # sécurité: conversation appartient bien à l'étudiant
        cur.execute("""
          SELECT
            c.id_conversation,
            r.id_responsable, r.nom, r.prenom, r.email,
            m.id_memoire, m.titre
          FROM isms.conversation c
          JOIN isms.responsable r ON r.id_responsable = c.id_responsable
          JOIN isms.memoire m ON m.id_memoire = c.id_memoire
          WHERE c.id_conversation = %s AND c.id_etudiant = %s
          LIMIT 1
        """, [id_conversation, etudiant_id])
        conv = cur.fetchone()

        if not conv:
            messages.error(request, "Conversation introuvable ou accès non autorisé.")
            return redirect("etudiant:messages_list")

        # marquer lus: messages envoyés par responsable
        cur.execute("""
          UPDATE isms.message
          SET is_read = TRUE
          WHERE id_conversation = %s
            AND sender_type = 'RESPONSABLE'
            AND is_read = FALSE
        """, [id_conversation])

        # messages
        cur.execute("""
          SELECT id_message, sender_type, sender_id, contenu, created_at, is_read
          FROM isms.message
          WHERE id_conversation = %s
          ORDER BY created_at ASC
        """, [id_conversation])
        msgs = fetchall_dict(cur)

    conversation = {
        "id_conversation": conv[0],
        "id_responsable": conv[1],
        "resp_nom": conv[2],
        "resp_prenom": conv[3],
        "resp_email": conv[4],
        "id_memoire": conv[5],
        "memoire_titre": conv[6],
    }

    return render(request, "etudiants/messages/detail.html", {
        "conversation": conversation,
        "messages_list": msgs,
        "me_id": etudiant_id,
    })


@require_POST
@etudiant_required
@admin_year_required
def messages_send(request, id_conversation: int):
    """
    Envoyer un message (étudiant).
    """
    etudiant_id = request.session.get("etudiant_id")
    contenu = (request.POST.get("contenu") or "").strip()

    if not contenu:
        messages.error(request, "Message vide.")
        return redirect("etudiant:messages_detail", id_conversation=id_conversation)

    try:
        with connection.cursor() as cur:
            # sécurité: conversation appartient bien à l'étudiant
            cur.execute("""
              SELECT 1
              FROM isms.conversation
              WHERE id_conversation=%s AND id_etudiant=%s
              LIMIT 1
            """, [id_conversation, etudiant_id])
            if cur.fetchone() is None:
                messages.error(request, "Accès non autorisé.")
                return redirect("etudiant:messages_list")

            cur.execute("""
              INSERT INTO isms.message (id_conversation, sender_type, sender_id, contenu)
              VALUES (%s, 'ETUDIANT', %s, %s)
            """, [id_conversation, etudiant_id, contenu])

        return redirect("etudiant:messages_detail", id_conversation=id_conversation)

    except DatabaseError:
        messages.error(request, "Erreur base de données lors de l’envoi.")
        return redirect("etudiant:messages_detail", id_conversation=id_conversation)
    





@require_POST
@etudiant_required
@admin_year_required
def conversation_start(request, id_memoire: int):
    """
    Étudiant: ouvre une conversation avec un encadrant/co-encadrant sur SON mémoire.
    POST: id_responsable
    """
    etudiant_id = request.session.get("etudiant_id")
    id_responsable = request.POST.get("id_responsable")

    if not id_responsable:
        messages.error(request, "Choisis un encadrant.")
        return redirect("etudiant:memoire_detail", id_memoire=id_memoire)

    try:
        with connection.cursor() as cur:
            # 1) vérifier que le mémoire appartient bien à l'étudiant (sécurité côté app)
            cur.execute("""
              SELECT 1
              FROM isms.memoire
              WHERE id_memoire=%s AND id_etudiant=%s
              LIMIT 1
            """, [id_memoire, etudiant_id])
            if cur.fetchone() is None:
                messages.error(request, "Mémoire introuvable ou accès non autorisé.")
                return redirect("etudiant:dashboard")

            # 2) vérifier que le responsable est encadrant/co-encadrant de ce mémoire
            cur.execute("""
              SELECT 1
              FROM isms.encadrement
              WHERE id_memoire=%s AND id_responsable=%s
                AND encadrement IN ('ENCADRANT','CO_ENCADRANT')
              LIMIT 1
            """, [id_memoire, id_responsable])
            if cur.fetchone() is None:
                messages.error(request, "Ce responsable n’est pas encadrant/co-encadrant de ce mémoire.")
                return redirect("etudiant:memoire_detail", id_memoire=id_memoire)

            # 3) créer la conversation si elle n'existe pas, puis récupérer son id
            # ON CONFLICT => pas de doublon (uq_conversation_triplet)
            cur.execute("""
              INSERT INTO isms.conversation (id_etudiant, id_responsable, id_memoire)
              VALUES (%s, %s, %s)
              ON CONFLICT (id_etudiant, id_responsable, id_memoire)
              DO UPDATE SET id_etudiant = EXCLUDED.id_etudiant
              RETURNING id_conversation
            """, [etudiant_id, id_responsable, id_memoire])
            conv_id = cur.fetchone()[0]

        return redirect("etudiant:messages_detail", id_conversation=conv_id)

    except DatabaseError:
        messages.error(request, "Erreur base de données lors de l’ouverture de la conversation.")
        return redirect("etudiant:memoire_detail", id_memoire=id_memoire)


# =========================================================
# ARCHIVE (MEMOIRES + RAPPORTS VALIDES)
# =========================================================
@etudiant_required
@admin_year_required
def archive_list(request):
    """
    Archive consultable par l'étudiant :
    - mémoires/rapports VALIDES
    - filtrable par année, département, type, mot-clé
    - option: uniquement ceux dont la soutenance est EFFECTUEE
    """
    # année courante en session (par défaut)
    session_annee_id = request.session.get("annee_id")

    q = (request.GET.get("q") or "").strip().lower()
    type_ = (request.GET.get("type") or "").strip()
    annee_id = (request.GET.get("annee_id") or "").strip()
    dep_id = (request.GET.get("dep_id") or "").strip()
    only_effectuee = (request.GET.get("only_effectuee") or "").strip()  # "1" ou ""

    # fallback: si annee_id non fourni => session year
    if not annee_id:
        annee_id = str(session_annee_id) if session_annee_id else ""

    where = ["m.statut = 'VALIDE'"]
    params = []

    if annee_id.isdigit():
        where.append("m.id_annee = %s")
        params.append(int(annee_id))

    if dep_id.isdigit():
        where.append("e.id_departement = %s")
        params.append(int(dep_id))

    if type_ in ("PFE", "MEMOIRE", "RAPPORT", "THESE"):
        where.append("m.type = %s")
        params.append(type_)

    if q:
        like = f"%{q}%"
        where.append("""
          (
            LOWER(m.titre) LIKE %s
            OR LOWER(COALESCE(m.description,'')) LIKE %s
            OR LOWER(e.nom) LIKE %s
            OR LOWER(e.prenom) LIKE %s
            OR LOWER(d.nom_departement) LIKE %s
            OR LOWER(a.libelle) LIKE %s
          )
        """)
        params.extend([like, like, like, like, like, like])

    # si only_effectuee = 1 => on exige soutenance EFFECTUEE
    # sinon on garde un LEFT JOIN (pour montrer aussi les VALIDES sans soutenance)
    join_soutenance = "LEFT JOIN isms.soutenance s ON s.id_memoire = m.id_memoire"
    if only_effectuee == "1":
        join_soutenance = "JOIN isms.soutenance s ON s.id_memoire = m.id_memoire"
        where.append("s.statut = 'EFFECTUEE'")

    sql = f"""
      SELECT
        m.id_memoire,
        m.titre,
        m.type,
        m.date_depot,
        m.fichier_pdf,
        a.id_annee,
        a.libelle AS annee_libelle,
        d.id_departement,
        d.nom_departement,
        e.id_etudiant,
        e.nom AS etu_nom,
        e.prenom AS etu_prenom,
        s.id_soutenance,
        s.statut AS soutenance_statut,
        s.date_ AS soutenance_date,
        s.heure AS soutenance_heure
      FROM isms.memoire m
      JOIN isms.etudiant e ON e.id_etudiant = m.id_etudiant
      JOIN isms.departement d ON d.id_departement = e.id_departement
      JOIN isms.annee_universitaire a ON a.id_annee = m.id_annee
      {join_soutenance}
      WHERE {" AND ".join(where)}
      ORDER BY a.libelle DESC, m.date_depot DESC
    """

    with connection.cursor() as cur:
        cur.execute(sql, params)
        rows = fetchall_dict(cur)

        # Pour alimenter les listes déroulantes
        cur.execute("SELECT id_annee, libelle FROM isms.annee_universitaire ORDER BY libelle DESC")
        annees = fetchall_dict(cur)

        cur.execute("SELECT id_departement, nom_departement FROM isms.departement ORDER BY nom_departement ASC")
        departements = fetchall_dict(cur)

    # Construire url PDF (champ TEXT)
    for r in rows:
        r["pdf_url"] = (settings.MEDIA_URL + r["fichier_pdf"]) if r.get("fichier_pdf") else ""

    return render(request, "etudiants/archive/list.html", {
        "rows": rows,
        "annees": annees,
        "departements": departements,
        "types": ["PFE", "MEMOIRE", "RAPPORT", "THESE"],

        "q": request.GET.get("q", ""),
        "type": type_,
        "annee_id": annee_id,
        "dep_id": dep_id,
        "only_effectuee": only_effectuee,
    })


@etudiant_required
@admin_year_required
def archive_detail(request, id_memoire: int):
    """
    Détail d'un mémoire/rapport validé (archive).
    """
    with connection.cursor() as cur:
        cur.execute("""
          SELECT
            m.id_memoire, m.titre, m.type, m.description, m.fichier_pdf, m.date_depot,
            a.id_annee, a.libelle AS annee_libelle,
            e.id_etudiant, e.nom AS etu_nom, e.prenom AS etu_prenom, e.email AS etu_email,
            d.id_departement, d.nom_departement
          FROM isms.memoire m
          JOIN isms.etudiant e ON e.id_etudiant = m.id_etudiant
          JOIN isms.departement d ON d.id_departement = e.id_departement
          JOIN isms.annee_universitaire a ON a.id_annee = m.id_annee
          WHERE m.id_memoire = %s AND m.statut = 'VALIDE'
          LIMIT 1
        """, [id_memoire])
        r = cur.fetchone()

        if not r:
            messages.error(request, "Archive introuvable.")
            return redirect("etudiant:archive_list")

        # Encadreurs
        cur.execute("""
          SELECT r2.id_responsable, r2.nom, r2.prenom, r2.email, en.encadrement
          FROM isms.encadrement en
          JOIN isms.responsable r2 ON r2.id_responsable = en.id_responsable
          WHERE en.id_memoire = %s
          ORDER BY en.encadrement, r2.nom, r2.prenom
        """, [id_memoire])
        encadreurs = fetchall_dict(cur)

        # Soutenance (si existe)
        cur.execute("""
          SELECT
            s.id_soutenance, s.date_, s.heure, s.statut,
            sa.nom_salle,
            j.nom_jury
          FROM isms.soutenance s
          JOIN isms.salle sa ON sa.id_salle = s.id_salle
          JOIN isms.jury j ON j.id_jury = s.id_jury
          WHERE s.id_memoire = %s
          LIMIT 1
        """, [id_memoire])
        s = cur.fetchone()

    mem = {
        "id_memoire": r[0],
        "titre": r[1],
        "type": r[2],
        "description": r[3],
        "fichier_pdf": r[4],
        "pdf_url": (settings.MEDIA_URL + r[4]) if r[4] else "",
        "date_depot": r[5],

        "id_annee": r[6],
        "annee_libelle": r[7],

        "id_etudiant": r[8],
        "etu_nom": r[9],
        "etu_prenom": r[10],
        "etu_email": r[11],

        "id_departement": r[12],
        "nom_departement": r[13],
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

    return render(request, "etudiants/archive/detail.html", {
        "mem": mem,
        "encadreurs": encadreurs,
        "soutenance": soutenance,
    })


# =========================================================
# MES SOUTENANCES (LISTE)
# =========================================================
@etudiant_required
@admin_year_required
def soutenance_list(request):
    annee_id = request.session.get("annee_id")
    etudiant_id = request.session.get("etudiant_id")

    statut = (request.GET.get("statut") or "").strip()
    q = (request.GET.get("q") or "").strip().lower()

    where = ["m.id_annee = %s", "m.id_etudiant = %s"]
    params = [annee_id, etudiant_id]

    if statut in ("PLANIFIEE", "EFFECTUEE", "ANNULEE"):
        where.append("s.statut = %s")
        params.append(statut)

    if q:
        like = f"%{q}%"
        where.append("(LOWER(m.titre) LIKE %s OR LOWER(j.nom_jury) LIKE %s OR LOWER(sa.nom_salle) LIKE %s)")
        params.extend([like, like, like])

    sql = f"""
      SELECT
        s.id_soutenance, s.date_, s.heure, s.statut,
        sa.nom_salle,
        j.nom_jury,
        m.id_memoire, m.titre, m.type
      FROM isms.soutenance s
      JOIN isms.memoire m ON m.id_memoire = s.id_memoire
      JOIN isms.salle sa ON sa.id_salle = s.id_salle
      JOIN isms.jury j ON j.id_jury = s.id_jury
      WHERE {" AND ".join(where)}
      ORDER BY s.date_ DESC, s.heure DESC
    """

    try:
        with connection.cursor() as cur:
            cur.execute(sql, params)
            rows = fetchall_dict(cur)
    except DatabaseError:
        messages.error(request, "Erreur base de données.")
        rows = []

    return render(request, "etudiants/soutenances/list.html", {
        "rows": rows,
        "STATUTS": ["PLANIFIEE", "EFFECTUEE", "ANNULEE"],
        "statut": statut,
        "q": request.GET.get("q", ""),
        "annee_libelle": request.session.get("annee_libelle"),
    })


# =========================================================
# DETAIL SOUTENANCE
# =========================================================
@etudiant_required
@admin_year_required
def soutenance_detail(request, id_soutenance: int):
    annee_id = request.session.get("annee_id")
    etudiant_id = request.session.get("etudiant_id")

    try:
        with connection.cursor() as cur:
            # 1) Base soutenance + mémoire + jury + salle + note finale (LEFT JOIN)
            cur.execute("""
              SELECT
                s.id_soutenance, s.date_, s.heure, s.statut,
                sa.nom_salle,
                j.id_jury, j.nom_jury,
                m.id_memoire, m.titre, m.type, m.statut AS mem_statut,
                n.note_finale, n.commentaire AS commentaire_final
              FROM isms.soutenance s
              JOIN isms.memoire m ON m.id_memoire = s.id_memoire
              JOIN isms.salle sa ON sa.id_salle = s.id_salle
              JOIN isms.jury j ON j.id_jury = s.id_jury
              LEFT JOIN isms.note n ON n.id_soutenance = s.id_soutenance
              WHERE s.id_soutenance = %s
                AND s.id_annee = %s
                AND m.id_etudiant = %s
              LIMIT 1
            """, [id_soutenance, annee_id, etudiant_id])
            r = cur.fetchone()

            if not r:
                messages.error(request, "Soutenance introuvable ou accès non autorisé.")
                return redirect("etudiant:soutenance_list")

            jury_id = r[5]

            # 2) Membres du jury (avec rôles M2M)
            cur.execute("""
              SELECT
                res.id_responsable, res.nom, res.prenom, res.email,
                COALESCE(string_agg(DISTINCT ro.libelle, ', '), '') AS roles
              FROM isms.composition_jury cj
              JOIN isms.responsable res ON res.id_responsable = cj.id_responsable
              LEFT JOIN isms.responsable_role rr ON rr.id_responsable = res.id_responsable
              LEFT JOIN isms.role ro ON ro.id_role = rr.id_role
              WHERE cj.id_jury = %s
              GROUP BY res.id_responsable, res.nom, res.prenom, res.email
              ORDER BY res.nom, res.prenom
            """, [jury_id])
            jury_membres = fetchall_dict(cur)

            # 3) Notes par membre du jury (si existantes)
            cur.execute("""
              SELECT
                nj.id_responsable,
                nj.note,
                nj.commentaire
              FROM isms.note_jury nj
              WHERE nj.id_soutenance = %s
              ORDER BY nj.id_responsable
            """, [id_soutenance])
            notes_jury = fetchall_dict(cur)

            # map pour affichage rapide par id_responsable
            notes_jury_map = {x["id_responsable"]: x for x in notes_jury}

            # moyenne harmonisée (si au moins une note)
            cur.execute("""
              SELECT ROUND(AVG(note)::numeric, 2)
              FROM isms.note_jury
              WHERE id_soutenance = %s
            """, [id_soutenance])
            moyenne = cur.fetchone()[0]

    except DatabaseError:
        messages.error(request, "Erreur base de données.")
        return redirect("etudiant:soutenance_list")

    soutenance = {
        "id_soutenance": r[0],
        "date_": r[1],
        "heure": r[2],
        "statut": r[3],
        "nom_salle": r[4],
        "nom_jury": r[6],
        "id_memoire": r[7],
        "titre": r[8],
        "memoire_type": r[9],
        "memoire_statut": r[10],
        "note_finale": r[11],
        "commentaire_final": r[12],
    }

    # ✅ items jury (membre + sa note)
    jury_items = [{"m": m, "nj": notes_jury_map.get(m["id_responsable"])} for m in jury_membres]

    return render(request, "etudiants/soutenances/detail.html", {
        "soutenance": soutenance,
        "jury_membres": jury_membres,
        "jury_items": jury_items,   # ✅ pour afficher les notes par membre
        "moyenne": moyenne,
        "annee_libelle": request.session.get("annee_libelle"),
    })