-- =========================================================
-- 04_security_roles.sql (VERSION CORRIGÉE)
-- Projet ISMS - Sécurité: rôles + permissions + vues sécurisées
-- =========================================================

BEGIN;

-- 0) Schéma
CREATE SCHEMA IF NOT EXISTS isms;

-- ---------------------------------------------------------
-- 1) Création des rôles
-- ---------------------------------------------------------

-- admin_db : administration complète
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'admin_db') THEN
    CREATE ROLE admin_db LOGIN PASSWORD 'admin_db_password';
  END IF;
END $$;

-- app_user : rôle utilisé par Django pour exécuter l'application
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
    CREATE ROLE app_user LOGIN PASSWORD 'app_user_password';
  END IF;
END $$;

-- ---------------------------------------------------------
-- 2) Droits de base sur la base et le schéma
-- ---------------------------------------------------------
-- NB: adapte le nom de la base si nécessaire
GRANT CONNECT ON DATABASE plateforme_memoire TO admin_db, app_user;

GRANT USAGE ON SCHEMA isms TO admin_db, app_user;

-- ---------------------------------------------------------
-- 3) Droits admin_db (tout sur le schéma)
-- ---------------------------------------------------------
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA isms TO admin_db;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA isms TO admin_db;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA isms TO admin_db;

ALTER DEFAULT PRIVILEGES IN SCHEMA isms
GRANT ALL PRIVILEGES ON TABLES TO admin_db;

ALTER DEFAULT PRIVILEGES IN SCHEMA isms
GRANT ALL PRIVILEGES ON SEQUENCES TO admin_db;

ALTER DEFAULT PRIVILEGES IN SCHEMA isms
GRANT ALL PRIVILEGES ON FUNCTIONS TO admin_db;

-- ---------------------------------------------------------
-- 4) Droits app_user (principe du moindre privilège)
-- ---------------------------------------------------------

-- Lecture par défaut
GRANT SELECT ON ALL TABLES IN SCHEMA isms TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA isms TO app_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA isms TO app_user;

-- Écriture tables opérationnelles
GRANT INSERT, UPDATE ON isms.memoire TO app_user;
GRANT INSERT, UPDATE ON isms.soutenance TO app_user;
GRANT INSERT, UPDATE ON isms.note TO app_user;
GRANT INSERT, UPDATE ON isms.note_jury TO app_user;

GRANT INSERT, UPDATE, DELETE ON isms.encadrement TO app_user;
GRANT INSERT, UPDATE, DELETE ON isms.composition_jury TO app_user;

-- selon ton besoin: création/MAJ des acteurs via app
GRANT INSERT, UPDATE ON isms.etudiant TO app_user;
GRANT INSERT, UPDATE ON isms.responsable TO app_user;
GRANT INSERT, UPDATE, DELETE ON isms.responsable_role TO app_user;

-- Tables de référence : lecture seule (annee, salle, departement, niveau, role, jury)
-- (donc pas de write ici)
REVOKE INSERT, UPDATE, DELETE ON isms.role FROM app_user;
REVOKE INSERT, UPDATE, DELETE ON isms.annee_universitaire FROM app_user;
REVOKE INSERT, UPDATE, DELETE ON isms.niveau FROM app_user;
REVOKE INSERT, UPDATE, DELETE ON isms.departement FROM app_user;
REVOKE INSERT, UPDATE, DELETE ON isms.salle FROM app_user;
REVOKE INSERT, UPDATE, DELETE ON isms.jury FROM app_user;

-- ---------------------------------------------------------
-- 5) Protéger les données sensibles: mot_de_pass
-- ---------------------------------------------------------
-- Stratégie:
-- 1) on retire SELECT sur tables sensibles
-- 2) on crée des vues sans mot_de_pass
-- 3) on donne SELECT sur ces vues à app_user

REVOKE SELECT ON isms.etudiant FROM app_user;
REVOKE SELECT ON isms.responsable FROM app_user;

-- Vues sécurisées (sans mot_de_pass)

-- ✅ Vue étudiant (SANS colonne filiere qui n'existe pas)
CREATE OR REPLACE VIEW isms.v_etudiant_public AS
SELECT
  id_etudiant,
  nom,
  prenom,
  email,
  telephone,
  niveau,
  id_departement,
  id_annee,
  created_at,
  updated_at
FROM isms.etudiant;

-- ✅ Vue responsable avec rôles via responsable_role (Many-to-Many)
CREATE OR REPLACE VIEW isms.v_responsable_public AS
SELECT
  r.id_responsable,
  r.nom,
  r.prenom,
  r.email,
  r.is_admin,
  r.created_at,
  r.updated_at,
  STRING_AGG(ro.code, ', ' ORDER BY ro.code) AS roles_codes,
  STRING_AGG(ro.libelle, ', ' ORDER BY ro.libelle) AS roles_libelles
FROM isms.responsable r
LEFT JOIN isms.responsable_role rr ON rr.id_responsable = r.id_responsable
LEFT JOIN isms.role ro ON ro.id_role = rr.id_role
GROUP BY r.id_responsable, r.nom, r.prenom, r.email, r.is_admin, r.created_at, r.updated_at;

GRANT SELECT ON isms.v_etudiant_public TO app_user;
GRANT SELECT ON isms.v_responsable_public TO app_user;

-- audit_log: lecture admin seulement
REVOKE ALL ON isms.audit_log FROM app_user;
GRANT SELECT ON isms.audit_log TO admin_db;

COMMIT;