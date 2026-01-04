from django.db import connection

def get_active_annee():
    with connection.cursor() as cur:
        cur.execute("""
            SELECT id_annee, libelle
            FROM isms.annee_universitaire
            WHERE active = TRUE
            LIMIT 1
        """)
        row = cur.fetchone()
    if not row:
        return None
    return {"id_annee": int(row[0]), "libelle": row[1]}
