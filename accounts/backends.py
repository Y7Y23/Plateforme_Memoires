from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.db import connection


class ISMSBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        email = (username or kwargs.get("email") or "").strip().lower()
        if not email or password is None:
            return None

        # ----- RESPONSABLE -----
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT r.id_responsable, r.email, r.mot_de_pass, r.is_admin, ro.code
                FROM isms.responsable r
                JOIN isms.role ro ON ro.id_role = r.id_role
                WHERE lower(r.email) = lower(%s)
                LIMIT 1;
                """,
                [email],
            )
            row = cur.fetchone()

        if row:
            rid, db_email, db_pass, is_admin, role_code = row
            if db_pass == password:
                user = self._get_or_create_user(db_email)
                if request is not None:
                    request.session["actor_type"] = "responsable"
                    request.session["responsable_id"] = int(rid)
                    request.session["is_admin"] = bool(is_admin)
                    request.session["role_code"] = role_code
                    request.session.pop("etudiant_id", None)
                return user

        # ----- ETUDIANT -----
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT id_etudiant, email, mot_de_pass
                FROM isms.etudiant
                WHERE lower(email) = lower(%s)
                LIMIT 1;
                """,
                [email],
            )
            row = cur.fetchone()

        if row:
            eid, db_email, db_pass = row
            if db_pass == password:
                user = self._get_or_create_user(db_email)
                if request is not None:
                    request.session["actor_type"] = "etudiant"
                    request.session["etudiant_id"] = int(eid)
                    request.session["is_admin"] = False
                    request.session["role_code"] = None
                    request.session.pop("responsable_id", None)
                return user

        return None

    def _get_or_create_user(self, email: str) -> User:
        user, _ = User.objects.get_or_create(
            username=email,
            defaults={"email": email, "is_active": True},
        )
        return user
