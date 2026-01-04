BEGIN;

-- 0) Schéma
CREATE SCHEMA IF NOT EXISTS isms;
SET search_path TO isms;

-- =========================================================
-- 1) Tables de référence
-- =========================================================

CREATE TABLE IF NOT EXISTS annee_universitaire (
    id_annee BIGSERIAL PRIMARY KEY,
    libelle  VARCHAR(20) NOT NULL UNIQUE
);

ALTER TABLE isms.annee_universitaire
  ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT FALSE;

-- Une seule année active
CREATE UNIQUE INDEX IF NOT EXISTS uq_annee_active
ON isms.annee_universitaire (active)
WHERE active = TRUE;

-- Activer automatiquement la dernière année si elle existe
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM isms.annee_universitaire) THEN
    UPDATE isms.annee_universitaire SET active = FALSE;
    UPDATE isms.annee_universitaire
      SET active = TRUE
    WHERE id_annee = (SELECT max(id_annee) FROM isms.annee_universitaire);
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS niveau (
    id_niveau BIGSERIAL PRIMARY KEY,
    libelle   VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS departement (
    id_departement  BIGSERIAL PRIMARY KEY,
    nom_departement VARCHAR(80) NOT NULL UNIQUE,
    id_niveau       BIGINT NOT NULL,
    CONSTRAINT fk_departement_niveau
      FOREIGN KEY (id_niveau) REFERENCES niveau(id_niveau)
      ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS salle (
    id_salle  BIGSERIAL PRIMARY KEY,
    nom_salle VARCHAR(60) NOT NULL UNIQUE
);

-- =========================================================
-- 2) Rôles (remplace Grade)
-- =========================================================

CREATE TABLE IF NOT EXISTS role (
    id_role BIGSERIAL PRIMARY KEY,
    code    VARCHAR(40) NOT NULL UNIQUE,
    libelle VARCHAR(120)
);

-- Ajout safe de la contrainte CHECK (PostgreSQL compatible)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_role_code'
          AND conrelid = 'isms.role'::regclass
    ) THEN
        ALTER TABLE isms.role
        ADD CONSTRAINT ck_role_code
        CHECK (code IN ('ADMIN','ENCADRANT','RAPPORTEUR','PRESIDENT','MEMBRE_JURY'));
    END IF;
END $$;

-- =========================================================
-- 3) Acteurs
-- =========================================================

CREATE TABLE IF NOT EXISTS etudiant (
    id_etudiant   BIGSERIAL PRIMARY KEY,
    nom           VARCHAR(60) NOT NULL,
    prenom        VARCHAR(60) NOT NULL,
    email         VARCHAR(120) NOT NULL UNIQUE,
    telephone     VARCHAR(30),
    niveau        VARCHAR(50),
    mot_de_pass   TEXT NOT NULL,
    id_departement BIGINT NOT NULL,
    id_annee       BIGINT NOT NULL,

    CONSTRAINT ck_etudiant_email CHECK (position('@' in email) > 1),

    CONSTRAINT fk_etudiant_departement
      FOREIGN KEY (id_departement) REFERENCES departement(id_departement)
      ON UPDATE CASCADE ON DELETE RESTRICT,

    CONSTRAINT fk_etudiant_annee
      FOREIGN KEY (id_annee) REFERENCES annee_universitaire(id_annee)
      ON UPDATE CASCADE ON DELETE RESTRICT
);

-- ✅ Table responsable (SANS id_role, AVEC is_admin)
CREATE TABLE IF NOT EXISTS responsable (
    id_responsable BIGSERIAL PRIMARY KEY,
    nom            VARCHAR(60) NOT NULL,
    prenom         VARCHAR(60) NOT NULL,
    email          VARCHAR(120) NOT NULL UNIQUE,
    mot_de_pass    TEXT NOT NULL,
    is_admin       BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT ck_responsable_email CHECK (position('@' in email) > 1)
);

-- ✅ Table de liaison Many-to-Many (responsable ↔ role)
CREATE TABLE IF NOT EXISTS responsable_role (
    id_responsable BIGINT NOT NULL,
    id_role        BIGINT NOT NULL,
    
    PRIMARY KEY (id_responsable, id_role),
    
    CONSTRAINT fk_resp_role_responsable
      FOREIGN KEY (id_responsable) REFERENCES responsable(id_responsable)
      ON UPDATE CASCADE ON DELETE CASCADE,
    
    CONSTRAINT fk_resp_role_role
      FOREIGN KEY (id_role) REFERENCES role(id_role)
      ON UPDATE CASCADE ON DELETE RESTRICT
);

-- ✅ Index pour optimiser les requêtes sur responsable_role
CREATE INDEX IF NOT EXISTS idx_responsable_role_responsable 
    ON responsable_role(id_responsable);
CREATE INDEX IF NOT EXISTS idx_responsable_role_role 
    ON responsable_role(id_role);

-- =========================================================
-- 4) Mémoire + Encadrement
-- =========================================================

CREATE TABLE IF NOT EXISTS memoire (
    id_memoire   BIGSERIAL PRIMARY KEY,
    titre        VARCHAR(255) NOT NULL,
    type         VARCHAR(30) NOT NULL,
    description  TEXT,
    fichier_pdf  TEXT,
    date_depot   TIMESTAMP NOT NULL DEFAULT NOW(),
    statut       VARCHAR(20) NOT NULL DEFAULT 'DEPOSE',
    id_etudiant  BIGINT NOT NULL,
    id_annee     BIGINT NOT NULL,

    CONSTRAINT ck_memoire_type
      CHECK (type IN ('PFE','MEMOIRE','RAPPORT','THESE')),

    CONSTRAINT ck_memoire_statut
      CHECK (statut IN ('DEPOSE','EN_VERIFICATION','VALIDE','REFUSE')),

    CONSTRAINT fk_memoire_etudiant
      FOREIGN KEY (id_etudiant) REFERENCES etudiant(id_etudiant)
      ON UPDATE CASCADE ON DELETE CASCADE,

    CONSTRAINT fk_memoire_annee
      FOREIGN KEY (id_annee) REFERENCES annee_universitaire(id_annee)
      ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS encadrement (
    id_responsable BIGINT NOT NULL,
    id_memoire     BIGINT NOT NULL,
    encadrement    VARCHAR(40) NOT NULL DEFAULT 'ENCADRANT',
    PRIMARY KEY (id_responsable, id_memoire),

    CONSTRAINT ck_encadrement_type
      CHECK (encadrement IN ('ENCADRANT','CO_ENCADRANT')),

    CONSTRAINT fk_encadrement_responsable
      FOREIGN KEY (id_responsable) REFERENCES responsable(id_responsable)
      ON UPDATE CASCADE ON DELETE CASCADE,

    CONSTRAINT fk_encadrement_memoire
      FOREIGN KEY (id_memoire) REFERENCES memoire(id_memoire)
      ON UPDATE CASCADE ON DELETE CASCADE
);

-- =========================================================
-- 5) Jury + Composition
-- =========================================================

CREATE TABLE IF NOT EXISTS jury (
    id_jury  BIGSERIAL PRIMARY KEY,
    nom_jury VARCHAR(120) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS composition_jury (
    id_responsable BIGINT NOT NULL,
    id_jury        BIGINT NOT NULL,
    PRIMARY KEY (id_responsable, id_jury),

    CONSTRAINT fk_comp_jury_responsable
      FOREIGN KEY (id_responsable) REFERENCES responsable(id_responsable)
      ON UPDATE CASCADE ON DELETE CASCADE,

    CONSTRAINT fk_comp_jury_jury
      FOREIGN KEY (id_jury) REFERENCES jury(id_jury)
      ON UPDATE CASCADE ON DELETE CASCADE
);

-- =========================================================
-- 6) Soutenance + Note
-- =========================================================

CREATE TABLE IF NOT EXISTS soutenance (
    id_soutenance BIGSERIAL PRIMARY KEY,
    date_         DATE NOT NULL,
    heure         TIME NOT NULL,
    statut        VARCHAR(20) NOT NULL DEFAULT 'PLANIFIEE',
    id_memoire    BIGINT NOT NULL UNIQUE,
    id_jury       BIGINT NOT NULL,
    id_annee      BIGINT NOT NULL,
    id_salle      BIGINT NOT NULL,

    CONSTRAINT ck_soutenance_statut
      CHECK (statut IN ('PLANIFIEE','EFFECTUEE','ANNULEE')),

    CONSTRAINT fk_soutenance_memoire
      FOREIGN KEY (id_memoire) REFERENCES memoire(id_memoire)
      ON UPDATE CASCADE ON DELETE CASCADE,

    CONSTRAINT fk_soutenance_jury
      FOREIGN KEY (id_jury) REFERENCES jury(id_jury)
      ON UPDATE CASCADE ON DELETE RESTRICT,

    CONSTRAINT fk_soutenance_annee
      FOREIGN KEY (id_annee) REFERENCES annee_universitaire(id_annee)
      ON UPDATE CASCADE ON DELETE RESTRICT,

    CONSTRAINT fk_soutenance_salle
      FOREIGN KEY (id_salle) REFERENCES salle(id_salle)
      ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS note (
    id_note       BIGSERIAL PRIMARY KEY,
    note_finale   NUMERIC(4,2) NOT NULL,
    commentaire   TEXT,
    id_soutenance BIGINT NOT NULL UNIQUE,

    CONSTRAINT ck_note_range CHECK (note_finale >= 0 AND note_finale <= 20),

    CONSTRAINT fk_note_soutenance
      FOREIGN KEY (id_soutenance) REFERENCES soutenance(id_soutenance)
      ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS note_jury (
    id_soutenance  BIGINT NOT NULL,
    id_responsable BIGINT NOT NULL,
    note           NUMERIC(4,2) NOT NULL,
    commentaire    TEXT,

    CONSTRAINT pk_note_jury
      PRIMARY KEY (id_soutenance, id_responsable),

    CONSTRAINT ck_note_jury_range
      CHECK (note >= 0 AND note <= 20),

    CONSTRAINT fk_note_jury_soutenance
      FOREIGN KEY (id_soutenance)
      REFERENCES soutenance(id_soutenance)
      ON UPDATE CASCADE
      ON DELETE CASCADE,

    CONSTRAINT fk_note_jury_responsable
      FOREIGN KEY (id_responsable)
      REFERENCES responsable(id_responsable)
      ON UPDATE CASCADE
      ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_note_jury_soutenance
    ON note_jury(id_soutenance);

CREATE INDEX IF NOT EXISTS idx_note_jury_responsable
    ON note_jury(id_responsable);

-- =========================================================
-- 7) Index
-- =========================================================

CREATE INDEX IF NOT EXISTS idx_etudiant_departement ON etudiant(id_departement);
CREATE INDEX IF NOT EXISTS idx_etudiant_annee       ON etudiant(id_annee);

CREATE INDEX IF NOT EXISTS idx_memoire_etudiant     ON memoire(id_etudiant);
CREATE INDEX IF NOT EXISTS idx_memoire_annee        ON memoire(id_annee);
CREATE INDEX IF NOT EXISTS idx_memoire_statut       ON memoire(statut);

CREATE INDEX IF NOT EXISTS idx_soutenance_date      ON soutenance(date_);
CREATE INDEX IF NOT EXISTS idx_soutenance_salle     ON soutenance(id_salle);
CREATE INDEX IF NOT EXISTS idx_soutenance_jury      ON soutenance(id_jury);

COMMIT;

-- =========================================================
-- 8) Données initiales (OPTIONNEL)
-- =========================================================

-- Insertion des rôles de base
INSERT INTO isms.role (code, libelle) VALUES
    ('ADMIN', 'Administrateur système'),
    ('ENCADRANT', 'Encadrant de mémoire'),
    ('RAPPORTEUR', 'Rapporteur de jury'),
    ('PRESIDENT', 'Président de jury'),
    ('MEMBRE_JURY', 'Membre de jury')
ON CONFLICT (code) DO NOTHING;

-- Vérification finale
DO $$
DECLARE
    nb_tables INTEGER;
    nb_roles INTEGER;
BEGIN
    -- Compter les tables créées
    SELECT COUNT(*) INTO nb_tables
    FROM information_schema.tables
    WHERE table_schema = 'isms';
    
    -- Compter les rôles
    SELECT COUNT(*) INTO nb_roles FROM isms.role;
    
    RAISE NOTICE '========================================';
    RAISE NOTICE 'CRÉATION DE LA BASE DE DONNÉES TERMINÉE';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Tables créées : %', nb_tables;
    RAISE NOTICE 'Rôles disponibles : %', nb_roles;
    RAISE NOTICE '';
    RAISE NOTICE '✅ Structure responsable_role créée (Many-to-Many)';
    RAISE NOTICE '✅ Colonne is_admin ajoutée à responsable';
    RAISE NOTICE '✅ Index optimisés créés';
    RAISE NOTICE '';
    RAISE NOTICE 'Prochaine étape : Créer un SuperAdmin';
    RAISE NOTICE 'Exemple SQL :';
    RAISE NOTICE '  INSERT INTO isms.responsable (nom, prenom, email, mot_de_pass, is_admin)';
    RAISE NOTICE '  VALUES (''Admin'', ''Système'', ''admin@isms.esp.mr'', ''votre_mdp'', TRUE);';
    RAISE NOTICE '';
    RAISE NOTICE '  INSERT INTO isms.responsable_role (id_responsable, id_role)';
    RAISE NOTICE '  VALUES (1, (SELECT id_role FROM isms.role WHERE code = ''ADMIN''));';
END $$;