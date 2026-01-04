-- =========================================================
-- 06_seed_test_data.sql (MAJ ROLE)
-- Projet ISMS - Données de test cohérentes
-- =========================================================

BEGIN;
SET search_path TO isms;

-- Nettoyage léger (optionnel)
-- (On supprime dans l'ordre pour respecter les FK)
DELETE FROM note;
DELETE FROM soutenance;
DELETE FROM composition_jury;
DELETE FROM jury;
DELETE FROM encadrement;
DELETE FROM memoire;
DELETE FROM etudiant;
DELETE FROM responsable;

-- Référentiels dépendants
DELETE FROM departement;
DELETE FROM niveau;
DELETE FROM salle;
DELETE FROM role;
DELETE FROM responsable_role;
DELETE FROM annee_universitaire;

-- ---------------------------------------------------------
-- 1) Référentiels
-- ---------------------------------------------------------
INSERT INTO annee_universitaire(libelle) VALUES
('2024-2025'),
('2025-2026');

-- (Optionnel) activer une année : ici 2024-2025
UPDATE annee_universitaire SET active = FALSE;
UPDATE annee_universitaire SET active = TRUE
WHERE libelle = '2024-2025';

INSERT INTO niveau(libelle) VALUES
('Licence'),
('Master');

INSERT INTO departement(nom_departement, id_niveau) VALUES
('Informatique', (SELECT id_niveau FROM niveau WHERE libelle='Master')),
('Gestion',      (SELECT id_niveau FROM niveau WHERE libelle='Licence'));

INSERT INTO salle(nom_salle) VALUES
('Salle A'),
('Salle B'),
('Amphi 1');

-- ---------------------------------------------------------
-- 2) Rôles applicatifs (table role)
-- codes attendus : ADMIN, ENCADRANT, RAPPORTEUR, PRESIDENT, MEMBRE_JURY
-- ---------------------------------------------------------
INSERT INTO role(code, libelle) VALUES
('ADMIN',       'Administrateur'),
('ENCADRANT',   'Encadrant'),
('RAPPORTEUR',  'Rapporteur'),
('PRESIDENT',   'Président de jury'),
('MEMBRE_JURY', 'Membre de jury');

-- ---------------------------------------------------------
-- 3) Responsables (jury + encadrants)
-- ---------------------------------------------------------
-- Insertion responsables (SANS id_role)
INSERT INTO responsable(nom, prenom, email, mot_de_pass, is_admin) VALUES
('Admin', 'Root', 'admin@isms.local', 'admin123', TRUE),
('El Amrani', 'Hassan', 'president@isms.local', 'pass123', FALSE),
('Bennani', 'Sara', 'rapporteur@isms.local', 'pass123', FALSE),
('Fathi', 'Youssef', 'membre1@isms.local', 'pass123', FALSE),
('Khaldi', 'Imane', 'encadrant1@isms.local', 'pass123', FALSE),
('Zaki', 'Nabil', 'encadrant2@isms.local', 'pass123', FALSE);

-- Attribution des rôles via responsable_role
INSERT INTO responsable_role(id_responsable, id_role)
SELECT r.id_responsable, ro.id_role
FROM responsable r
CROSS JOIN role ro
WHERE (r.email = 'admin@isms.local' AND ro.code = 'ADMIN')
   OR (r.email = 'president@isms.local' AND ro.code = 'PRESIDENT')
   OR (r.email = 'rapporteur@isms.local' AND ro.code = 'RAPPORTEUR')
   OR (r.email = 'membre1@isms.local' AND ro.code = 'MEMBRE_JURY')
   OR (r.email = 'encadrant1@isms.local' AND ro.code = 'ENCADRANT')
   OR (r.email = 'encadrant2@isms.local' AND ro.code = 'ENCADRANT');
-- ---------------------------------------------------------
-- 4) Étudiants
-- ---------------------------------------------------------
INSERT INTO etudiant(nom, prenom, email, telephone,niveau, mot_de_pass, id_departement, id_annee)
VALUES
('Alaoui', 'Yassine', 'yassine.alaoui@etudiant.local', '0600000001',  'Master',
 'pass123',
 (SELECT id_departement FROM departement WHERE nom_departement='Informatique'),
 (SELECT id_annee FROM annee_universitaire WHERE libelle='2024-2025')),

('Haddad', 'Meryem', 'meryem.haddad@etudiant.local', '0600000002', 'Licence',
 'pass123',
 (SELECT id_departement FROM departement WHERE nom_departement='Gestion'),
 (SELECT id_annee FROM annee_universitaire WHERE libelle='2024-2025'));

-- ---------------------------------------------------------
-- 5) Mémoires
-- statuts: DEPOSE, EN_VERIFICATION, VALIDE, REFUSE
-- ---------------------------------------------------------
INSERT INTO memoire(titre, type, description, fichier_pdf, statut, id_etudiant, id_annee)
VALUES
('Plateforme Universitaire de Dépôt de Mémoires', 'MEMOIRE',
 'Projet ISMS : dépôt, soutenance, notes, jury.', 'memoires/memoire1.pdf',
 'VALIDE',
 (SELECT id_etudiant FROM etudiant WHERE email='yassine.alaoui@etudiant.local'),
 (SELECT id_annee FROM annee_universitaire WHERE libelle='2024-2025')),

('Optimisation des processus administratifs', 'RAPPORT',
 'Rapport de fin d''études.', 'memoires/rapport1.pdf',
 'EN_VERIFICATION',
 (SELECT id_etudiant FROM etudiant WHERE email='meryem.haddad@etudiant.local'),
 (SELECT id_annee FROM annee_universitaire WHERE libelle='2024-2025'));

-- ---------------------------------------------------------
-- 6) Encadrement (au moins 1 encadrant par mémoire)
-- Neutralité: encadrant ne doit pas être membre jury de ce mémoire
-- ---------------------------------------------------------
INSERT INTO encadrement(id_responsable, id_memoire, encadrement)
VALUES
((SELECT id_responsable FROM responsable WHERE email='encadrant1@isms.local'),
 (SELECT id_memoire FROM memoire WHERE titre='Plateforme Universitaire de Dépôt de Mémoires'),
 'ENCADRANT'),

((SELECT id_responsable FROM responsable WHERE email='encadrant2@isms.local'),
 (SELECT id_memoire FROM memoire WHERE titre='Optimisation des processus administratifs'),
 'ENCADRANT');

-- ---------------------------------------------------------
-- 7) Jury + composition (>=3 membres + PRESIDENT + RAPPORTEUR)
-- ---------------------------------------------------------
INSERT INTO jury(nom_jury) VALUES
('Jury Master SI - Session 1');

INSERT INTO composition_jury(id_responsable, id_jury)
SELECT r.id_responsable, j.id_jury
FROM responsable r
CROSS JOIN jury j
WHERE j.nom_jury = 'Jury Master SI - Session 1'
  AND r.email IN ('president@isms.local','rapporteur@isms.local','membre1@isms.local');

-- ---------------------------------------------------------
-- 8) Soutenances (PLANIFIEE dans le futur + mémoire VALIDE)
-- ---------------------------------------------------------
INSERT INTO soutenance(date_, heure, statut, id_memoire, id_jury, id_annee, id_salle)
VALUES
(CURRENT_DATE + 7, '10:00', 'PLANIFIEE',
 (SELECT id_memoire FROM memoire WHERE titre='Plateforme Universitaire de Dépôt de Mémoires'),
 (SELECT id_jury FROM jury WHERE nom_jury='Jury Master SI - Session 1'),
 (SELECT id_annee FROM annee_universitaire WHERE libelle='2024-2025'),
 (SELECT id_salle FROM salle WHERE nom_salle='Salle A'));

-- ---------------------------------------------------------
-- 9) Exemple complet : soutenance EFFECTUEE + note
-- ---------------------------------------------------------
INSERT INTO memoire(titre, type, description, fichier_pdf, statut, id_etudiant, id_annee)
VALUES
('Système de gestion de soutenances', 'PFE',
 'PFE démonstration note finale.', 'memoires/pfe2.pdf',
 'VALIDE',
 (SELECT id_etudiant FROM etudiant WHERE email='meryem.haddad@etudiant.local'),
 (SELECT id_annee FROM annee_universitaire WHERE libelle='2024-2025'));

INSERT INTO encadrement(id_responsable, id_memoire, encadrement)
VALUES
((SELECT id_responsable FROM responsable WHERE email='encadrant2@isms.local'),
 (SELECT id_memoire FROM memoire WHERE titre='Système de gestion de soutenances'),
 'ENCADRANT');

INSERT INTO jury(nom_jury) VALUES
('Jury Licence - Session 2');

INSERT INTO composition_jury(id_responsable, id_jury)
SELECT r.id_responsable, j.id_jury
FROM responsable r
CROSS JOIN jury j
WHERE j.nom_jury = 'Jury Licence - Session 2'
  AND r.email IN ('president@isms.local','rapporteur@isms.local','membre1@isms.local');

-- Soutenance EFFECTUEE (date peut être passée)
INSERT INTO soutenance(date_, heure, statut, id_memoire, id_jury, id_annee, id_salle)
VALUES
(CURRENT_DATE - 2, '14:00', 'EFFECTUEE',
 (SELECT id_memoire FROM memoire WHERE titre='Système de gestion de soutenances'),
 (SELECT id_jury FROM jury WHERE nom_jury='Jury Licence - Session 2'),
 (SELECT id_annee FROM annee_universitaire WHERE libelle='2024-2025'),
 (SELECT id_salle FROM salle WHERE nom_salle='Amphi 1'));

-- Note (autorisé car soutenance EFFECTUEE)
INSERT INTO note(note_finale, commentaire, id_soutenance)
VALUES
(16.50, 'Très bonne présentation et bon travail.',
 (SELECT s.id_soutenance
  FROM soutenance s
  JOIN memoire m ON m.id_memoire = s.id_memoire
  WHERE m.titre = 'Système de gestion de soutenances'
  LIMIT 1));

COMMIT;
