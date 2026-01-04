-- =========================================================
-- 05_views_dashboards.sql (PGADMIN SAFE - MAJ ROLE)
-- Projet ISMS - Vues analytiques + Vue matérialisée
-- =========================================================

SET search_path TO isms;

-- ---------------------------------------------------------
-- 0) Nettoyage : drop dans l'ordre (dépendances)
-- ---------------------------------------------------------
DROP VIEW IF EXISTS isms.v_soutenances_a_venir CASCADE;
DROP VIEW IF EXISTS isms.v_notes_finales CASCADE;
DROP VIEW IF EXISTS isms.v_soutenances_details CASCADE;
DROP VIEW IF EXISTS isms.v_jury_composition_resume CASCADE;
DROP VIEW IF EXISTS isms.v_memoires_par_statut CASCADE;
DROP VIEW IF EXISTS isms.v_memoires_details CASCADE;

DROP MATERIALIZED VIEW IF EXISTS isms.mv_stats_departement CASCADE;

-- (Optionnel) si tu veux repartir clean sur la fonction aussi
DROP FUNCTION IF EXISTS isms.fn_refresh_stats();


-- ---------------------------------------------------------
-- 1) Vue: mémoires (détails complets + étudiant + département + année)
-- ---------------------------------------------------------
CREATE VIEW isms.v_memoires_details AS
SELECT
  m.id_memoire,
  m.titre,
  m.type,
  m.statut,
  m.date_depot,
  m.fichier_pdf,
  e.id_etudiant,
  e.nom AS etudiant_nom,
  e.prenom AS etudiant_prenom,
  e.email AS etudiant_email,
  d.id_departement,
  d.nom_departement,
  a.id_annee,
  a.libelle AS annee_universitaire
FROM isms.memoire m
JOIN isms.etudiant e ON e.id_etudiant = m.id_etudiant
JOIN isms.departement d ON d.id_departement = e.id_departement
JOIN isms.annee_universitaire a ON a.id_annee = m.id_annee;


-- ---------------------------------------------------------
-- 2) Vue: mémoires par statut (compteur)
-- ---------------------------------------------------------
CREATE VIEW isms.v_memoires_par_statut AS
SELECT
  m.id_annee,
  a.libelle AS annee_universitaire,
  m.statut,
  COUNT(*) AS total
FROM isms.memoire m
JOIN isms.annee_universitaire a ON a.id_annee = m.id_annee
GROUP BY m.id_annee, a.libelle, m.statut
ORDER BY a.libelle, m.statut;


-- ---------------------------------------------------------
-- 3) Vue: soutenances (détails + mémoire + salle + jury)
-- ---------------------------------------------------------
CREATE VIEW isms.v_soutenances_details AS
SELECT
  s.id_soutenance,
  s.date_,
  s.heure,
  (s.date_::timestamp + s.heure) AS datetime_soutenance,
  s.statut AS statut_soutenance,
  sa.id_salle,
  sa.nom_salle,
  j.id_jury,
  j.nom_jury,
  m.id_memoire,
  m.titre AS memoire_titre,
  m.type  AS memoire_type,
  m.statut AS statut_memoire,
  e.id_etudiant,
  e.nom AS etudiant_nom,
  e.prenom AS etudiant_prenom,
  e.email AS etudiant_email,
  a.id_annee,
  a.libelle AS annee_universitaire
FROM isms.soutenance s
JOIN isms.salle sa ON sa.id_salle = s.id_salle
JOIN isms.jury j ON j.id_jury = s.id_jury
JOIN isms.memoire m ON m.id_memoire = s.id_memoire
JOIN isms.etudiant e ON e.id_etudiant = m.id_etudiant
JOIN isms.annee_universitaire a ON a.id_annee = s.id_annee;


-- ---------------------------------------------------------
-- 4) Vue: soutenances à venir (PLANIFIEE + futur)
-- ---------------------------------------------------------
CREATE VIEW isms.v_soutenances_a_venir AS
SELECT *
FROM isms.v_soutenances_details
WHERE statut_soutenance = 'PLANIFIEE'
  AND datetime_soutenance > NOW()
ORDER BY datetime_soutenance;


-- ---------------------------------------------------------
-- 5) Vue: notes finales (soutenance + note)
-- ---------------------------------------------------------
CREATE VIEW isms.v_notes_finales AS
SELECT
  sd.id_soutenance,
  sd.date_,
  sd.heure,
  sd.datetime_soutenance,
  sd.nom_salle,
  sd.nom_jury,
  sd.id_memoire,
  sd.memoire_titre,
  sd.id_etudiant,
  sd.etudiant_nom,
  sd.etudiant_prenom,
  sd.annee_universitaire,
  n.note_finale,
  n.commentaire
FROM isms.v_soutenances_details sd
LEFT JOIN isms.note n ON n.id_soutenance = sd.id_soutenance;


-- ---------------------------------------------------------
-- 6) Vue: jury avec nombre de membres + rôles (MAJ ROLE)
-- ---------------------------------------------------------
CREATE VIEW isms.v_jury_composition_resume AS
SELECT
  j.id_jury,
  j.nom_jury,
  COUNT(DISTINCT cj.id_responsable) AS nb_membres,
  COUNT(DISTINCT CASE WHEN ro.code = 'PRESIDENT' THEN cj.id_responsable END) AS nb_presidents,
  COUNT(DISTINCT CASE WHEN ro.code = 'RAPPORTEUR' THEN cj.id_responsable END) AS nb_rapporteurs
FROM isms.jury j
LEFT JOIN isms.composition_jury cj ON cj.id_jury = j.id_jury
LEFT JOIN isms.responsable_role rr ON rr.id_responsable = cj.id_responsable
LEFT JOIN isms.role ro ON ro.id_role = rr.id_role
GROUP BY j.id_jury, j.nom_jury
ORDER BY j.nom_jury;

-- ---------------------------------------------------------
-- 7) Vue matérialisée (statistiques rapides par département et année)
-- ---------------------------------------------------------
CREATE MATERIALIZED VIEW isms.mv_stats_departement AS
SELECT
  a.id_annee,
  a.libelle AS annee_universitaire,
  d.id_departement,
  d.nom_departement,
  COUNT(m.id_memoire) AS total_memoires,
  SUM(CASE WHEN m.statut = 'VALIDE' THEN 1 ELSE 0 END) AS memoires_valides,
  SUM(CASE WHEN m.statut = 'REFUSE' THEN 1 ELSE 0 END) AS memoires_refuses,
  SUM(CASE WHEN m.statut = 'EN_VERIFICATION' THEN 1 ELSE 0 END) AS memoires_en_verification,
  SUM(CASE WHEN m.statut = 'DEPOSE' THEN 1 ELSE 0 END) AS memoires_deposes
FROM isms.departement d
JOIN isms.etudiant e ON e.id_departement = d.id_departement
JOIN isms.memoire m ON m.id_etudiant = e.id_etudiant
JOIN isms.annee_universitaire a ON a.id_annee = m.id_annee
GROUP BY a.id_annee, a.libelle, d.id_departement, d.nom_departement;

-- Index pour accélérer les filtres sur la MV
CREATE INDEX IF NOT EXISTS idx_mv_stats_annee ON isms.mv_stats_departement(id_annee);
CREATE INDEX IF NOT EXISTS idx_mv_stats_dept  ON isms.mv_stats_departement(id_departement);


-- Fonction pour rafraîchir la vue matérialisée
CREATE OR REPLACE FUNCTION isms.fn_refresh_stats()
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
  REFRESH MATERIALIZED VIEW isms.mv_stats_departement;
END;
$$;
