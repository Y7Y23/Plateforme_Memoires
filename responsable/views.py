from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import connection, IntegrityError, DatabaseError
from django.views.decorators.http import require_POST

from accounts.decorators import responsable_required, admin_year_required


# ---------- helpers ----------
def fetchall_dict(cur):
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _get_role_codes(request):
    rc = request.session.get("role_codes") or []
    if rc is None:
        return []

    # déjà une liste python
    if isinstance(rc, (list, tuple)):
        return [str(x).strip() for x in rc if str(x).strip()]

    # string : "ENCADRANT" ou "{ENCADRANT,MEMBRE_JURY}"
    if isinstance(rc, str):
        s = rc.strip()

        # format array postgres : {A,B,C}
        if s.startswith("{") and s.endswith("}"):
            s = s[1:-1].strip()
            if not s:
                return []
            parts = [p.strip().strip('"') for p in s.split(",")]
            return [p for p in parts if p]

        # string simple
        return [s] if s else []

    # fallback
    return []


def _has_role(request, *codes: str) -> bool:
    if request.session.get("is_admin"):
        return True
    role_codes = _get_role_codes(request)
    return any(code in role_codes for code in codes)
    """
    Many-to-Many roles: role_codes = ['ENCADRANT','PRESIDENT',...]
    + is_admin = True permet tout.
    """
    if request.session.get("is_admin"):
        return True

    role_codes = request.session.get("role_codes") or []
    # sécurité: si parfois role_codes arrive en string
    if isinstance(role_codes, str):
        role_codes = [role_codes]

    return any(code in role_codes for code in codes)


def _require_role(request, *codes: str, msg: str = "Accès refusé."):
    if not _has_role(request, *codes):
        messages.error(request, msg)
        return False
    return True


# =========================================================
# DASHBOARD (ENCADRANT)
# =========================================================
@responsable_required
@admin_year_required
def dashboard(request):
    role_codes = request.session.get("role_codes") or []
    if isinstance(role_codes, str):
        role_codes = [role_codes]

    annee_id = request.session.get("annee_id")
    responsable_id = request.session.get("responsable_id")

    stats = {"nb_memoires": 0, "nb_attente": 0, "nb_valides": 0, "nb_refuses": 0}

    # ✅ Encadrant/Co-encadrant : même rôle "ENCADRANT" mais stats sur ses encadrements
    if _has_role(request, "ENCADRANT"):
        with connection.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*)
                FROM isms.encadrement en
                JOIN isms.memoire m ON m.id_memoire = en.id_memoire
                WHERE en.id_responsable = %s AND m.id_annee = %s
            """, [responsable_id, annee_id])
            stats["nb_memoires"] = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*)
                FROM isms.encadrement en
                JOIN isms.memoire m ON m.id_memoire = en.id_memoire
                WHERE en.id_responsable = %s AND m.id_annee = %s
                  AND m.statut IN ('DEPOSE','EN_VERIFICATION')
            """, [responsable_id, annee_id])
            stats["nb_attente"] = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*)
                FROM isms.encadrement en
                JOIN isms.memoire m ON m.id_memoire = en.id_memoire
                WHERE en.id_responsable = %s AND m.id_annee = %s
                  AND m.statut = 'VALIDE'
            """, [responsable_id, annee_id])
            stats["nb_valides"] = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*)
                FROM isms.encadrement en
                JOIN isms.memoire m ON m.id_memoire = en.id_memoire
                WHERE en.id_responsable = %s AND m.id_annee = %s
                  AND m.statut = 'REFUSE'
            """, [responsable_id, annee_id])
            stats["nb_refuses"] = cur.fetchone()[0]

    return render(request, "responsables/dashboard.html", {
        **stats,
        "role_codes": role_codes,
        "is_admin": bool(request.session.get("is_admin")),
        "annee_id": annee_id,
        "annee_libelle": request.session.get("annee_libelle"),
        "can_encadrant": _has_role(request, "ENCADRANT"),
        "can_jury": _has_role(request, "MEMBRE_JURY"),
    })


# =========================================================
# MEMOIRES (ENCADRANT)
# =========================================================
@responsable_required
@admin_year_required
def memoire_list(request):
    if not _require_role(request, "ENCADRANT", msg="Accès réservé aux encadrants."):
        return redirect("accounts:post_login")

    annee_id = request.session.get("annee_id")
    responsable_id = request.session.get("responsable_id")

    q = (request.GET.get("q") or "").strip().lower()
    statut = (request.GET.get("statut") or "").strip()

    where = ["m.id_annee = %s", "en.id_responsable = %s"]
    params = [annee_id, responsable_id]

    if statut:
        where.append("m.statut = %s")
        params.append(statut)

    if q:
        like = f"%{q}%"
        where.append("""
            (LOWER(m.titre) LIKE %s
             OR LOWER(e.nom) LIKE %s
             OR LOWER(e.prenom) LIKE %s
             OR LOWER(e.email) LIKE %s)
        """)
        params.extend([like, like, like, like])

    sql = f"""
        SELECT
            m.id_memoire, m.titre, m.type, m.statut, m.date_depot,
            e.id_etudiant, e.nom, e.prenom, e.email,
            en.encadrement
        FROM isms.encadrement en
        JOIN isms.memoire m ON m.id_memoire = en.id_memoire
        JOIN isms.etudiant e ON e.id_etudiant = m.id_etudiant
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
        "id_etudiant": r[5],
        "etu_nom": r[6],
        "etu_prenom": r[7],
        "etu_email": r[8],
        "encadrement": r[9],
    } for r in rows]

    return render(request, "responsables/memoires/list.html", {
        "memoires": memoires,
        "q": request.GET.get("q", ""),
        "statut": statut,
        "STATUTS": ["DEPOSE", "EN_VERIFICATION", "VALIDE", "REFUSE"],
    })


@responsable_required
@admin_year_required
def memoire_detail(request, id_memoire: int):
    if not _require_role(request, "ENCADRANT", msg="Accès réservé aux encadrants."):
        return redirect("accounts:post_login")

    annee_id = request.session.get("annee_id")
    responsable_id = request.session.get("responsable_id")

    with connection.cursor() as cur:
        cur.execute("""
            SELECT
              m.id_memoire, m.titre, m.type, m.description, m.fichier_pdf, m.date_depot, m.statut,
              e.id_etudiant, e.nom, e.prenom, e.email,
              en.encadrement
            FROM isms.encadrement en
            JOIN isms.memoire m ON m.id_memoire = en.id_memoire
            JOIN isms.etudiant e ON e.id_etudiant = m.id_etudiant
            WHERE m.id_memoire = %s
              AND m.id_annee = %s
              AND en.id_responsable = %s
            LIMIT 1
        """, [id_memoire, annee_id, responsable_id])
        r = cur.fetchone()

        # afficher aussi les autres encadrants/co-encadrants du mémoire
        cur.execute("""
            SELECT r2.id_responsable, r2.nom, r2.prenom, r2.email, en2.encadrement
            FROM isms.encadrement en2
            JOIN isms.responsable r2 ON r2.id_responsable = en2.id_responsable
            WHERE en2.id_memoire = %s
            ORDER BY en2.encadrement, r2.nom, r2.prenom
        """, [id_memoire])
        encadreurs = fetchall_dict(cur)

    if not r:
        messages.error(request, "Mémoire introuvable ou accès non autorisé.")
        return redirect("responsable:memoire_list")

    memoire = {
        "id_memoire": r[0],
        "titre": r[1],
        "type": r[2],
        "description": r[3],
        "fichier_pdf": r[4],
        "date_depot": r[5],
        "statut": r[6],
        "id_etudiant": r[7],
        "etu_nom": r[8],
        "etu_prenom": r[9],
        "etu_email": r[10],
        "encadrement": r[11],
    }

    return render(request, "responsables/memoires/detail.html", {
        "memoire": memoire,
        "encadreurs": encadreurs,
    })


@require_POST
@responsable_required
@admin_year_required
def memoire_decision(request, id_memoire: int):
    if not _require_role(request, "ENCADRANT", msg="Accès réservé aux encadrants."):
        return redirect("accounts:post_login")

    annee_id = request.session.get("annee_id")
    responsable_id = request.session.get("responsable_id")

    decision = (request.POST.get("decision") or "").strip()
    if decision not in ("VALIDE", "REFUSE"):
        messages.error(request, "Décision invalide.")
        return redirect("responsable:memoire_detail", id_memoire=id_memoire)

    with connection.cursor() as cur:
        # vérifier périmètre (responsable est bien encadrant/co-encadrant de ce mémoire)
        cur.execute("""
            SELECT 1
            FROM isms.encadrement en
            JOIN isms.memoire m ON m.id_memoire = en.id_memoire
            WHERE m.id_memoire = %s AND m.id_annee = %s AND en.id_responsable = %s
            LIMIT 1
        """, [id_memoire, annee_id, responsable_id])
        if cur.fetchone() is None:
            messages.error(request, "Accès non autorisé.")
            return redirect("responsable:memoire_list")

        cur.execute("""
            UPDATE isms.memoire
            SET statut = %s
            WHERE id_memoire = %s AND id_annee = %s
        """, [decision, id_memoire, annee_id])

    messages.success(request, f"Décision appliquée : {decision}.")
    return redirect("responsable:memoire_detail", id_memoire=id_memoire)


# =========================================================
# SOUTENANCES + JURY (PRESIDENT)
# =========================================================
@responsable_required
@admin_year_required
def soutenance_list(request):
    if not _require_role(request, "PRESIDENT", msg="Accès réservé au président."):
        return redirect("accounts:post_login")

    annee_id = request.session.get("annee_id")
    q = (request.GET.get("q") or "").strip().lower()

    where = ["s.id_annee = %s"]
    params = [annee_id]

    if q:
        like = f"%{q}%"
        where.append("(LOWER(m.titre) LIKE %s OR LOWER(e.nom) LIKE %s OR LOWER(e.prenom) LIKE %s)")
        params.extend([like, like, like])

    sql = f"""
      SELECT
        s.id_soutenance, s.date_, s.heure, s.statut,
        sa.nom_salle,
        m.id_memoire, m.titre,
        e.nom, e.prenom,
        j.nom_jury
      FROM isms.soutenance s
      JOIN isms.memoire m ON m.id_memoire = s.id_memoire
      JOIN isms.etudiant e ON e.id_etudiant = m.id_etudiant
      JOIN isms.salle sa ON sa.id_salle = s.id_salle
      JOIN isms.jury j ON j.id_jury = s.id_jury
      WHERE {" AND ".join(where)}
      ORDER BY s.date_ DESC, s.heure DESC
    """

    with connection.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    soutenances = [{
        "id_soutenance": r[0],
        "date_": r[1],
        "heure": r[2],
        "statut": r[3],
        "nom_salle": r[4],
        "id_memoire": r[5],
        "titre": r[6],
        "etu_nom": r[7],
        "etu_prenom": r[8],
        "nom_jury": r[9],
    } for r in rows]

    return render(request, "responsables/soutenances/list.html", {
        "soutenances": soutenances,
        "q": q
    })

# =========================================================
# MEMBRE_JURY — MES SOUTENANCES + NOTE_JURY
# =========================================================
@responsable_required
@admin_year_required
def my_soutenances(request):
    if not _require_role(request, "MEMBRE_JURY", msg="Accès réservé aux membres de jury."):
        return redirect("responsable:dashboard")

    annee_id = request.session.get("annee_id")
    responsable_id = request.session.get("responsable_id")
    q = (request.GET.get("q") or "").strip().lower()
    statut = (request.GET.get("statut") or "").strip()

    where = ["s.id_annee = %s", "cj.id_responsable = %s"]
    params = [annee_id, responsable_id]

    if statut in ("PLANIFIEE", "EFFECTUEE", "ANNULEE"):
        where.append("s.statut = %s")
        params.append(statut)

    if q:
        like = f"%{q}%"
        where.append("(LOWER(m.titre) LIKE %s OR LOWER(e.nom) LIKE %s OR LOWER(e.prenom) LIKE %s)")
        params.extend([like, like, like])

    sql = f"""
      SELECT
        s.id_soutenance, s.date_, s.heure, s.statut,
        sa.nom_salle,
        m.id_memoire, m.titre,
        e.nom AS etu_nom, e.prenom AS etu_prenom,
        j.nom_jury,
        nj.note AS ma_note
      FROM isms.soutenance s
      JOIN isms.jury j ON j.id_jury = s.id_jury
      JOIN isms.composition_jury cj ON cj.id_jury = s.id_jury
      JOIN isms.memoire m ON m.id_memoire = s.id_memoire
      JOIN isms.etudiant e ON e.id_etudiant = m.id_etudiant
      JOIN isms.salle sa ON sa.id_salle = s.id_salle
      LEFT JOIN isms.note_jury nj
        ON nj.id_soutenance = s.id_soutenance AND nj.id_responsable = %s
      WHERE {" AND ".join(where)}
      ORDER BY s.date_ DESC, s.heure DESC
    """

    with connection.cursor() as cur:
        cur.execute(sql, [responsable_id] + params)
        rows = cur.fetchall()

    soutenances = [{
        "id_soutenance": r[0],
        "date_": r[1],
        "heure": r[2],
        "statut": r[3],
        "nom_salle": r[4],
        "id_memoire": r[5],
        "titre": r[6],
        "etu_nom": r[7],
        "etu_prenom": r[8],
        "nom_jury": r[9],
        "ma_note": r[10],
    } for r in rows]

    return render(request, "responsables/soutenances/list.html", {
        "soutenances": soutenances,
        "q": q,
        "statut": statut,
        "STATUTS": ["PLANIFIEE", "EFFECTUEE", "ANNULEE"],
    })


@responsable_required
@admin_year_required
def my_soutenance_detail(request, id_soutenance: int):
    if not _require_role(request, "MEMBRE_JURY", msg="Accès réservé aux membres de jury."):
        return redirect("responsable:dashboard")

    annee_id = request.session.get("annee_id")
    responsable_id = request.session.get("responsable_id")

    with connection.cursor() as cur:
        cur.execute("""
          SELECT 1
          FROM isms.soutenance s
          JOIN isms.composition_jury cj ON cj.id_jury = s.id_jury
          WHERE s.id_soutenance = %s AND s.id_annee = %s AND cj.id_responsable = %s
          LIMIT 1
        """, [id_soutenance, annee_id, responsable_id])
        if cur.fetchone() is None:
            messages.error(request, "Accès non autorisé à cette soutenance.")
            return redirect("responsable:my_soutenances")

        cur.execute("""
          SELECT
            s.id_soutenance, s.date_, s.heure, s.statut,
            sa.nom_salle,
            j.id_jury, j.nom_jury,
            m.id_memoire, m.titre, m.type, m.description, m.fichier_pdf,
            e.id_etudiant, e.nom, e.prenom, e.email
          FROM isms.soutenance s
          JOIN isms.salle sa ON sa.id_salle = s.id_salle
          JOIN isms.jury j ON j.id_jury = s.id_jury
          JOIN isms.memoire m ON m.id_memoire = s.id_memoire
          JOIN isms.etudiant e ON e.id_etudiant = m.id_etudiant
          WHERE s.id_soutenance = %s AND s.id_annee = %s
          LIMIT 1
        """, [id_soutenance, annee_id])
        r = cur.fetchone()

        cur.execute("""
          SELECT r.id_responsable, r.nom, r.prenom, r.email
          FROM isms.composition_jury cj
          JOIN isms.responsable r ON r.id_responsable = cj.id_responsable
          WHERE cj.id_jury = %s
          ORDER BY r.nom, r.prenom
        """, [r[5]])
        membres = fetchall_dict(cur)

        cur.execute("""
          SELECT note, commentaire
          FROM isms.note_jury
          WHERE id_soutenance = %s AND id_responsable = %s
          LIMIT 1
        """, [id_soutenance, responsable_id])
        note_row = cur.fetchone()

    base = {
    "id_soutenance": r[0],
    "date_": r[1],
    "heure": r[2],
    "statut": r[3],
    "nom_salle": r[4],
    "id_jury": r[5],
    "nom_jury": r[6],
    "id_memoire": r[7],
    "titre": r[8],
    "type": r[9],
    "description": r[10],
    "fichier_pdf": r[11].replace('memoires/memoires/', 'memoires/') if r[11] else None,  # ← FIX ICI
    "id_etudiant": r[12],
    "etu_nom": r[13],
    "etu_prenom": r[14],
    "etu_email": r[15],
    }

    my_note = None
    if note_row:
        my_note = {"note": note_row[0], "commentaire": note_row[1]}

    return render(request, "responsables/soutenances/detail.html", {
        "base": base,
        "membres": membres,
        "my_note": my_note,
    })


@require_POST
@responsable_required
@admin_year_required
def my_soutenance_note(request, id_soutenance: int):
    if not _require_role(request, "MEMBRE_JURY", msg="Accès réservé aux membres de jury."):
        return redirect("responsable:dashboard")

    annee_id = request.session.get("annee_id")
    responsable_id = request.session.get("responsable_id")

    note_str = (request.POST.get("note") or "").strip().replace(",", ".")
    commentaire = (request.POST.get("commentaire") or "").strip()

    try:
        note_val = float(note_str)
    except ValueError:
        messages.error(request, "Note invalide.")
        return redirect("responsable:my_soutenance_detail", id_soutenance=id_soutenance)

    if note_val < 0 or note_val > 20:
        messages.error(request, "La note doit être entre 0 et 20.")
        return redirect("responsable:my_soutenance_detail", id_soutenance=id_soutenance)

    with connection.cursor() as cur:
        cur.execute("""
          SELECT 1
          FROM isms.soutenance s
          JOIN isms.composition_jury cj ON cj.id_jury = s.id_jury
          WHERE s.id_soutenance = %s AND s.id_annee = %s AND cj.id_responsable = %s
          LIMIT 1
        """, [id_soutenance, annee_id, responsable_id])
        if cur.fetchone() is None:
            messages.error(request, "Accès non autorisé.")
            return redirect("responsable:my_soutenances")

        cur.execute("""
          INSERT INTO isms.note_jury (id_soutenance, id_responsable, note, commentaire)
          VALUES (%s, %s, %s, %s)
          ON CONFLICT (id_soutenance, id_responsable)
          DO UPDATE SET note = EXCLUDED.note, commentaire = EXCLUDED.commentaire
        """, [id_soutenance, responsable_id, note_val, commentaire or None])

    messages.success(request, "Votre note a été enregistrée.")
    return redirect("responsable:my_soutenance_detail", id_soutenance=id_soutenance)




# ========================================================= Messages (etudiant) =========================================================
@responsable_required
@admin_year_required
def messages_list(request):
    responsable_id = request.session.get("responsable_id")
    q = (request.GET.get("q") or "").strip().lower()

    where = ["c.id_responsable = %s"]
    params = [responsable_id]

    if q:
        like = f"%{q}%"
        where.append("(LOWER(e.nom) LIKE %s OR LOWER(e.prenom) LIKE %s OR LOWER(m.titre) LIKE %s)")
        params.extend([like, like, like])

    sql = f"""
      SELECT
        c.id_conversation,
        c.created_at,
        e.id_etudiant, e.nom, e.prenom, e.email,
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
            AND mm.sender_type = 'ETUDIANT'
            AND mm.is_read = FALSE
        ) AS unread_count
      FROM isms.conversation c
      JOIN isms.etudiant e ON e.id_etudiant = c.id_etudiant
      JOIN isms.memoire m ON m.id_memoire = c.id_memoire
      WHERE {" AND ".join(where)}
      ORDER BY last_at DESC NULLS LAST, c.created_at DESC
    """

    with connection.cursor() as cur:
        cur.execute(sql, params)
        conversations = fetchall_dict(cur)

    return render(request, "responsables/messages/list.html", {
        "conversations": conversations,
        "q": request.GET.get("q", ""),
    })


@responsable_required
@admin_year_required
def messages_detail(request, id_conversation: int):
    responsable_id = request.session.get("responsable_id")

    with connection.cursor() as cur:
        # sécurité: conversation appartient au responsable
        cur.execute("""
          SELECT
            c.id_conversation,
            e.id_etudiant, e.nom, e.prenom, e.email,
            m.id_memoire, m.titre
          FROM isms.conversation c
          JOIN isms.etudiant e ON e.id_etudiant = c.id_etudiant
          JOIN isms.memoire m ON m.id_memoire = c.id_memoire
          WHERE c.id_conversation = %s AND c.id_responsable = %s
          LIMIT 1
        """, [id_conversation, responsable_id])
        conv = cur.fetchone()

        if not conv:
            messages.error(request, "Conversation introuvable ou accès non autorisé.")
            return redirect("responsable:messages_list")

        # marquer lus: messages envoyés par étudiant
        cur.execute("""
          UPDATE isms.message
          SET is_read = TRUE
          WHERE id_conversation = %s
            AND sender_type = 'ETUDIANT'
            AND is_read = FALSE
        """, [id_conversation])

        cur.execute("""
          SELECT id_message, sender_type, sender_id, contenu, created_at, is_read
          FROM isms.message
          WHERE id_conversation = %s
          ORDER BY created_at ASC
        """, [id_conversation])
        msgs = fetchall_dict(cur)

    conversation = {
        "id_conversation": conv[0],
        "id_etudiant": conv[1],
        "etu_nom": conv[2],
        "etu_prenom": conv[3],
        "etu_email": conv[4],
        "id_memoire": conv[5],
        "memoire_titre": conv[6],
    }

    return render(request, "responsables/messages/detail.html", {
        "conversation": conversation,
        "messages_list": msgs,
        "me_id": responsable_id,
    })


@require_POST
@responsable_required
@admin_year_required
def messages_send(request, id_conversation: int):
    responsable_id = request.session.get("responsable_id")
    contenu = (request.POST.get("contenu") or "").strip()

    if not contenu:
        messages.error(request, "Message vide.")
        return redirect("responsable:messages_detail", id_conversation=id_conversation)

    try:
        with connection.cursor() as cur:
            cur.execute("""
              SELECT 1
              FROM isms.conversation
              WHERE id_conversation=%s AND id_responsable=%s
              LIMIT 1
            """, [id_conversation, responsable_id])
            if cur.fetchone() is None:
                messages.error(request, "Accès non autorisé.")
                return redirect("responsable:messages_list")

            cur.execute("""
              INSERT INTO isms.message (id_conversation, sender_type, sender_id, contenu)
              VALUES (%s, 'RESPONSABLE', %s, %s)
            """, [id_conversation, responsable_id, contenu])

        return redirect("responsable:messages_detail", id_conversation=id_conversation)

    except DatabaseError:
        messages.error(request, "Erreur base de données lors de l’envoi.")
        return redirect("responsable:messages_detail", id_conversation=id_conversation)
    



@require_POST
@responsable_required
@admin_year_required
def conversation_start(request, id_memoire: int):
    """
    Responsable: ouvre une conversation avec l’étudiant du mémoire.
    Autorisé seulement si le responsable encadre / co-encadre ce mémoire.
    """
    responsable_id = request.session.get("responsable_id")

    try:
        with connection.cursor() as cur:
            # 1) vérifier que ce responsable encadre ce mémoire
            cur.execute("""
              SELECT 1
              FROM isms.encadrement
              WHERE id_memoire=%s AND id_responsable=%s
                AND encadrement IN ('ENCADRANT','CO_ENCADRANT')
              LIMIT 1
            """, [id_memoire, responsable_id])
            if cur.fetchone() is None:
                messages.error(request, "Accès non autorisé (vous n’êtes pas encadrant de ce mémoire).")
                return redirect("responsable:memoire_list")

            # 2) récupérer l'étudiant du mémoire
            cur.execute("""
              SELECT id_etudiant
              FROM isms.memoire
              WHERE id_memoire=%s
              LIMIT 1
            """, [id_memoire])
            row = cur.fetchone()
            if not row:
                messages.error(request, "Mémoire introuvable.")
                return redirect("responsable:memoire_list")

            etudiant_id = row[0]

            # 3) créer la conversation (ou récupérer via ON CONFLICT)
            cur.execute("""
              INSERT INTO isms.conversation (id_etudiant, id_responsable, id_memoire)
              VALUES (%s, %s, %s)
              ON CONFLICT (id_etudiant, id_responsable, id_memoire)
              DO UPDATE SET id_etudiant = EXCLUDED.id_etudiant
              RETURNING id_conversation
            """, [etudiant_id, responsable_id, id_memoire])
            conv_id = cur.fetchone()[0]

        return redirect("responsable:messages_detail", id_conversation=conv_id)

    except DatabaseError:
        messages.error(request, "Erreur base de données lors de l’ouverture de la conversation.")
        return redirect("responsable:memoire_list")