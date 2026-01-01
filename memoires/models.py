from django.db import models


# =========================
# Référentiels
# =========================

class AnneeUniversitaire(models.Model):
    id_annee = models.BigAutoField(primary_key=True)
    libelle = models.CharField(max_length=20, unique=True)
    active = models.BooleanField(default=False)

    class Meta:
        db_table = "annee_universitaire"

    def __str__(self):
        return self.libelle


class Niveau(models.Model):
    id_niveau = models.BigAutoField(primary_key=True)
    libelle = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = "niveau"

    def __str__(self):
        return self.libelle


class Departement(models.Model):
    id_departement = models.BigAutoField(primary_key=True)
    nom_departement = models.CharField(max_length=80, unique=True)
    id_niveau = models.ForeignKey(Niveau, on_delete=models.PROTECT, db_column="id_niveau", related_name="departements")

    class Meta:
        db_table = "departement"

    def __str__(self):
        return self.nom_departement


class Salle(models.Model):
    id_salle = models.BigAutoField(primary_key=True)
    nom_salle = models.CharField(max_length=60, unique=True)

    class Meta:
        db_table = "salle"

    def __str__(self):
        return self.nom_salle


class Role(models.Model):
    id_role = models.BigAutoField(primary_key=True)
    code = models.CharField(max_length=40, unique=True)
    libelle = models.CharField(max_length=120, null=True, blank=True)

    # Colonnes ajoutées dans audit_triggers.sql (si tu les as gardées)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "role"

    def __str__(self):
        return self.code


# =========================
# Acteurs
# =========================

class Etudiant(models.Model):
    id_etudiant = models.BigAutoField(primary_key=True)
    nom = models.CharField(max_length=60)
    prenom = models.CharField(max_length=60)
    email = models.EmailField(max_length=120, unique=True)
    telephone = models.CharField(max_length=30, null=True, blank=True)
    filiere = models.CharField(max_length=80, null=True, blank=True)
    niveau = models.CharField(max_length=50, null=True, blank=True)  # texte (comme ton schéma)
    mot_de_pass = models.TextField()

    id_departement = models.ForeignKey(Departement, on_delete=models.PROTECT, db_column="id_departement", related_name="etudiants")
    id_annee = models.ForeignKey(AnneeUniversitaire, on_delete=models.PROTECT, db_column="id_annee", related_name="etudiants")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "etudiant"

    def __str__(self):
        return f"{self.nom} {self.prenom}"


class Responsable(models.Model):
    id_responsable = models.BigAutoField(primary_key=True)
    nom = models.CharField(max_length=60)
    prenom = models.CharField(max_length=60)
    email = models.EmailField(max_length=120, unique=True)
    mot_de_pass = models.TextField()

    id_role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        db_column="id_role",
        related_name="responsables"
    )

    is_admin = models.BooleanField(default=False)  # 👈 IMPORTANT

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "responsable"

    def __str__(self):
        flag = "ADMIN" if self.is_admin else self.id_role.code
        return f"{self.nom} {self.prenom} ({flag})"
    id_responsable = models.BigAutoField(primary_key=True)
    nom = models.CharField(max_length=60)
    prenom = models.CharField(max_length=60)
    email = models.EmailField(max_length=120, unique=True)
    mot_de_pass = models.TextField()

    id_role = models.ForeignKey(Role, on_delete=models.PROTECT, db_column="id_role", related_name="responsables")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "responsable"

    def __str__(self):
        return f"{self.nom} {self.prenom} ({self.id_role.code})"


# =========================
# Mémoire + Encadrement
# =========================

class Memoire(models.Model):
    class TypeMemoire(models.TextChoices):
        PFE = "PFE", "PFE"
        MEMOIRE = "MEMOIRE", "Mémoire"
        RAPPORT = "RAPPORT", "Rapport"
        THESE = "THESE", "Thèse"

    class StatutMemoire(models.TextChoices):
        DEPOSE = "DEPOSE", "Déposé"
        EN_VERIFICATION = "EN_VERIFICATION", "En vérification"
        VALIDE = "VALIDE", "Validé"
        REFUSE = "REFUSE", "Refusé"

    id_memoire = models.BigAutoField(primary_key=True)
    titre = models.CharField(max_length=255)
    type = models.CharField(max_length=30, choices=TypeMemoire.choices)
    description = models.TextField(null=True, blank=True)
    fichier_pdf = models.TextField(null=True, blank=True)
    date_depot = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=20, choices=StatutMemoire.choices, default=StatutMemoire.DEPOSE)

    id_etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE, db_column="id_etudiant", related_name="memoires")
    id_annee = models.ForeignKey(AnneeUniversitaire, on_delete=models.PROTECT, db_column="id_annee", related_name="memoires")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "memoire"

    def __str__(self):
        return self.titre


class Encadrement(models.Model):
    class TypeEncadrement(models.TextChoices):
        ENCADRANT = "ENCADRANT", "Encadrant"
        CO_ENCADRANT = "CO_ENCADRANT", "Co-encadrant"

    id_responsable = models.ForeignKey(Responsable, on_delete=models.CASCADE, db_column="id_responsable")
    id_memoire = models.ForeignKey(Memoire, on_delete=models.CASCADE, db_column="id_memoire")
    encadrement = models.CharField(max_length=40, choices=TypeEncadrement.choices, default=TypeEncadrement.ENCADRANT)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "encadrement"
        unique_together = (("id_responsable", "id_memoire"),)

    def __str__(self):
        return f"{self.id_responsable} - {self.id_memoire} ({self.encadrement})"


# =========================
# Jury + Composition
# =========================

class Jury(models.Model):
    id_jury = models.BigAutoField(primary_key=True)
    nom_jury = models.CharField(max_length=120, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "jury"

    def __str__(self):
        return self.nom_jury


class CompositionJury(models.Model):
    id_responsable = models.ForeignKey(Responsable, on_delete=models.CASCADE, db_column="id_responsable")
    id_jury = models.ForeignKey(Jury, on_delete=models.CASCADE, db_column="id_jury")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "composition_jury"
        unique_together = (("id_responsable", "id_jury"),)

    def __str__(self):
        return f"{self.id_jury} - {self.id_responsable}"


# =========================
# Soutenance + Note
# =========================

class Soutenance(models.Model):
    class StatutSoutenance(models.TextChoices):
        PLANIFIEE = "PLANIFIEE", "Planifiée"
        EFFECTUEE = "EFFECTUEE", "Effectuée"
        ANNULEE = "ANNULEE", "Annulée"

    id_soutenance = models.BigAutoField(primary_key=True)
    date = models.DateField(db_column="date_")
    heure = models.TimeField()
    statut = models.CharField(max_length=20, choices=StatutSoutenance.choices, default=StatutSoutenance.PLANIFIEE)

    # 1 soutenance par mémoire (Unique dans la DB)
    id_memoire = models.OneToOneField(Memoire, on_delete=models.CASCADE, db_column="id_memoire", related_name="soutenance")
    id_jury = models.ForeignKey(Jury, on_delete=models.PROTECT, db_column="id_jury", related_name="soutenances")
    id_annee = models.ForeignKey(AnneeUniversitaire, on_delete=models.PROTECT, db_column="id_annee", related_name="soutenances")
    id_salle = models.ForeignKey(Salle, on_delete=models.PROTECT, db_column="id_salle", related_name="soutenances")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "soutenance"

    def __str__(self):
        return f"Soutenance {self.id_soutenance} - {self.id_memoire.titre}"


class Note(models.Model):
    id_note = models.BigAutoField(primary_key=True)
    note_finale = models.DecimalField(max_digits=4, decimal_places=2)
    commentaire = models.TextField(null=True, blank=True)

    # 1 note par soutenance (Unique dans la DB)
    id_soutenance = models.OneToOneField(Soutenance, on_delete=models.CASCADE, db_column="id_soutenance", related_name="note")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "note"

    def __str__(self):
        return f"Note {self.note_finale}/20"


