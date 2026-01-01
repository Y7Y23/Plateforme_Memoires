-- =========================================================
-- 03_functions_business.sql
-- Projet ISMS - Fonctions métier (PL/pgSQL)
-- =========================================================

BEGIN;
SET search_path TO isms;

-- ---------------------------------------------------------
-- A) Validation / Refus mémoire (workflow contrôlé)
-- ---------------------------------------------------------

-- Valider un mémoire : EN_VERIFICATION -> VALIDE
CREATE OR REPLACE FUNCTION fn_valider_memoire(p_id_memoire BIGINT)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_statut TEXT;
BEGIN
  SELECT statut INTO v_statut
  FROM memoire
  WHERE id_memoire = p_id_memoire;

  IF v_statut IS NULL THEN
    RAISE EXCEPTION 'Mémoire introuvable (id=%).', p_id_memoire;
  END IF;

  IF v_statut <> 'EN_VERIFICATION' THEN
    RAISE EXCEPTION 'Validation impossible: le mémoire doit être EN_VERIFICATION (actuel=%).', v_statut;
  END IF;

  UPDATE memoire
  SET statut = 'VALIDE'
  WHERE id_memoire = p_id_memoire;
END;
$$;

-- Refuser un mémoire : EN_VERIFICATION -> REFUSE
-- On stocke le motif dans description (simple) si tu ne veux pas créer une table dédiée
CREATE OR REPLACE FUNCTION fn_refuser_memoire(p_id_memoire BIGINT, p_motif TEXT)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_statut TEXT;
BEGIN
  SELECT statut INTO v_statut
  FROM memoire
  WHERE id_memoire = p_id_memoire;

  IF v_statut IS NULL THEN
    RAISE EXCEPTION 'Mémoire introuvable (id=%).', p_id_memoire;
  END IF;

  IF v_statut <> 'EN_VERIFICATION' THEN
    RAISE EXCEPTION 'Refus impossible: le mémoire doit être EN_VERIFICATION (actuel=%).', v_statut;
  END IF;

  UPDATE memoire
  SET statut = 'REFUSE',
      description = COALESCE(description, '') || E'\n[MOTIF_REFUS] ' || COALESCE(p_motif,'(non précisé)')
  WHERE id_memoire = p_id_memoire;
END;
$$;

-- Mettre un mémoire en vérification (DEPOSE/REFUSE -> EN_VERIFICATION)
CREATE OR REPLACE FUNCTION fn_mettre_en_verification(p_id_memoire BIGINT)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_statut TEXT;
BEGIN
  SELECT statut INTO v_statut
  FROM memoire
  WHERE id_memoire = p_id_memoire;

  IF v_statut IS NULL THEN
    RAISE EXCEPTION 'Mémoire introuvable (id=%).', p_id_memoire;
  END IF;

  IF v_statut NOT IN ('DEPOSE','REFUSE') THEN
    RAISE EXCEPTION 'Action impossible: statut doit être DEPOSE ou REFUSE (actuel=%).', v_statut;
  END IF;

  UPDATE memoire
  SET statut = 'EN_VERIFICATION'
  WHERE id_memoire = p_id_memoire;
END;
$$;


-- ---------------------------------------------------------
-- B) Planification soutenance (création contrôlée)
-- ---------------------------------------------------------

-- Créer une soutenance en vérifiant les contraintes métier
CREATE OR REPLACE FUNCTION fn_planifier_soutenance(
  p_id_memoire BIGINT,
  p_id_jury BIGINT,
  p_id_annee BIGINT,
  p_id_salle BIGINT,
  p_date DATE,
  p_heure TIME
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
  v_statut_memoire TEXT;
  v_new_id BIGINT;
BEGIN
  -- Vérifier mémoire
  SELECT statut INTO v_statut_memoire
  FROM memoire WHERE id_memoire = p_id_memoire;

  IF v_statut_memoire IS NULL THEN
    RAISE EXCEPTION 'Mémoire introuvable (id_memoire=%).', p_id_memoire;
  END IF;

  IF v_statut_memoire <> 'VALIDE' THEN
    RAISE EXCEPTION 'Mémoire doit être VALIDE pour planifier une soutenance (statut=%).', v_statut_memoire;
  END IF;

  -- Insertion : les triggers vont vérifier jury, conflit salle, date future etc.
  INSERT INTO soutenance(date_, heure, statut, id_memoire, id_jury, id_annee, id_salle)
  VALUES (p_date, p_heure, 'PLANIFIEE', p_id_memoire, p_id_jury, p_id_annee, p_id_salle)
  RETURNING id_soutenance INTO v_new_id;

  RETURN v_new_id;
END;
$$;


-- Marquer soutenance comme EFFECTUEE (workflow)
CREATE OR REPLACE FUNCTION fn_marquer_soutenance_effectuee(p_id_soutenance BIGINT)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_exists INT;
BEGIN
  SELECT COUNT(*) INTO v_exists
  FROM soutenance
  WHERE id_soutenance = p_id_soutenance;

  IF v_exists = 0 THEN
    RAISE EXCEPTION 'Soutenance introuvable (id=%).', p_id_soutenance;
  END IF;

  UPDATE soutenance
  SET statut = 'EFFECTUEE'
  WHERE id_soutenance = p_id_soutenance;
END;
$$;


-- Annuler une soutenance
CREATE OR REPLACE FUNCTION fn_annuler_soutenance(p_id_soutenance BIGINT, p_motif TEXT)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_exists INT;
BEGIN
  SELECT COUNT(*) INTO v_exists
  FROM soutenance
  WHERE id_soutenance = p_id_soutenance;

  IF v_exists = 0 THEN
    RAISE EXCEPTION 'Soutenance introuvable (id=%).', p_id_soutenance;
  END IF;

  UPDATE soutenance
  SET statut = 'ANNULEE'
  WHERE id_soutenance = p_id_soutenance;

  -- on log aussi le motif via audit naturellement, mais on peut stocker le motif en description mémoire si besoin
  -- Ici on le met dans audit uniquement (audit_log garde new_data). Option: ajouter colonne "motif_annulation".
END;
$$;


-- ---------------------------------------------------------
-- C) Notes : calcul et enregistrement propre
-- ---------------------------------------------------------

-- Calculer la note finale d'une soutenance
-- (dans ton modèle actuel: 1 table note avec note_finale)
CREATE OR REPLACE FUNCTION fn_calcul_note_finale(p_id_soutenance BIGINT)
RETURNS NUMERIC(4,2)
LANGUAGE plpgsql
AS $$
DECLARE
  v_note NUMERIC(4,2);
BEGIN
  SELECT note_finale INTO v_note
  FROM note
  WHERE id_soutenance = p_id_soutenance;

  IF v_note IS NULL THEN
    RAISE EXCEPTION 'Aucune note enregistrée pour cette soutenance (id=%).', p_id_soutenance;
  END IF;

  RETURN v_note;
END;
$$;


-- Upsert note (insert si inexistante, update sinon)
-- Les triggers déjà en place vont bloquer si soutenance != EFFECTUEE
CREATE OR REPLACE FUNCTION fn_enregistrer_note(
  p_id_soutenance BIGINT,
  p_note NUMERIC(4,2),
  p_commentaire TEXT DEFAULT NULL
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
  IF p_note < 0 OR p_note > 20 THEN
    RAISE EXCEPTION 'Note invalide: doit être entre 0 et 20.';
  END IF;

  INSERT INTO note(note_finale, commentaire, id_soutenance)
  VALUES (p_note, p_commentaire, p_id_soutenance)
  ON CONFLICT (id_soutenance)
  DO UPDATE SET note_finale = EXCLUDED.note_finale,
                commentaire = EXCLUDED.commentaire,
                updated_at = NOW();
END;
$$;

COMMIT;
