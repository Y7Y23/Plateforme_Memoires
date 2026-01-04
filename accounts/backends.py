from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.db import connection


class ISMSBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        email = (username or kwargs.get("email") or "").strip().lower()
        password = "" if password is None else str(password)

        if not email:
            return None

        # =========================================================
        # 1) RESPONSABLE (prioritaire)
        # =========================================================
        with connection.cursor() as cur:
            cur.execute("""
                SELECT 
                    r.id_responsable,
                    r.nom,
                    r.prenom,
                    r.email,
                    r.mot_de_pass,
                    r.is_admin,
                    COALESCE(
                        array_agg(DISTINCT ro.code ORDER BY ro.code) 
                        FILTER (WHERE ro.code IS NOT NULL),
                        '{}'
                    ) AS role_codes
                FROM isms.responsable r
                LEFT JOIN isms.responsable_role rr ON rr.id_responsable = r.id_responsable
                LEFT JOIN isms.role ro ON ro.id_role = rr.id_role
                WHERE lower(r.email) = lower(%s)
                GROUP BY r.id_responsable, r.nom, r.prenom, r.email, r.mot_de_pass, r.is_admin
                LIMIT 1;
            """, [email])
            row = cur.fetchone()

        if row:
            rid, nom, prenom, db_email, db_pass, is_admin, role_codes = row

            # Mot de passe (plain text selon ton modèle actuel)
            if str(db_pass) == password:
                user = self._get_or_create_user(db_email)

                if request is not None:
                    self._reset_actor_session(request)

                    request.session["actor_type"] = "responsable"
                    request.session["responsable_id"] = int(rid)
                    request.session["is_admin"] = bool(is_admin)

                    # ✅ toujours une liste de strings
                    request.session["role_codes"] = list(role_codes) if role_codes else []

                    # ✅ utiles pour l'affichage UI (sidebar / header)
                    request.session["responsable_nom"] = nom
                    request.session["responsable_prenom"] = prenom
                    request.session["email"] = db_email

                return user

        # =========================================================
        # 2) ETUDIANT
        # =========================================================
        with connection.cursor() as cur:
            cur.execute("""
                SELECT id_etudiant, nom, prenom, email, mot_de_pass
                FROM isms.etudiant
                WHERE lower(email) = lower(%s)
                LIMIT 1;
            """, [email])
            row = cur.fetchone()

        if row:
            eid, nom, prenom, db_email, db_pass = row

            if str(db_pass) == password:
                user = self._get_or_create_user(db_email)

                if request is not None:
                    self._reset_actor_session(request)

                    request.session["actor_type"] = "etudiant"
                    request.session["etudiant_id"] = int(eid)

                    # ✅ cohérence avec responsable
                    request.session["is_admin"] = False
                    request.session["role_codes"] = []

                    # ✅ infos UI
                    request.session["etudiant_nom"] = nom
                    request.session["etudiant_prenom"] = prenom
                    request.session["email"] = db_email

                return user

        return None

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    def _reset_actor_session(self, request):
        """
        Nettoie proprement les clés liées à l'acteur pour éviter
        des conflits (ex: responsable_id restant en session quand on log étudiant).
        """
        keys = [
            "responsable_id", "is_admin", "role_codes",
            "responsable_nom", "responsable_prenom",
            "etudiant_id",
            "etudiant_nom", "etudiant_prenom",
            "actor_type",
            "email",
        ]
        for k in keys:
            request.session.pop(k, None)

    def _get_or_create_user(self, email: str) -> User:
        """
        Crée ou récupère un utilisateur Django minimal pour utiliser login().
        """
        user, _ = User.objects.get_or_create(
            username=email,
            defaults={"email": email, "is_active": True},
        )
        return user
