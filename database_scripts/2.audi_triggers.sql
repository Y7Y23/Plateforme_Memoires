-- =========================================================
-- 02_audit_triggers.sql  (VERSION OPTIMALE - MAJ ROLE)
-- Projet ISMS - Audit + Triggers + Règles métier
-- =========================================================

BEGIN;
SET search_path TO isms;

-- ---------------------------------------------------------
-- A) Colonnes techniques (created_at / updated_at)
-- ---------------------------------------------------------

ALTER TABLE etudiant
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW();

ALTER TABLE responsable
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW();

ALTER TABLE memoire
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW();

ALTER TABLE soutenance
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW();

ALTER TABLE note
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW();

-- Optionnel mais recommandé (audit & maintenance)
ALTER TABLE role
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW();

ALTER TABLE jury
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW();

ALTER TABLE encadrement
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW();

ALTER TABLE composition_jury
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW();


-- ---------------------------------------------------------
-- B) AUDIT (journal automatique)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
  id_audit    BIGSERIAL PRIMARY KEY,
  event_time  TIMESTAMP NOT NULL DEFAULT NOW(),
  username    TEXT NOT NULL DEFAULT current_user,
  action      TEXT NOT NULL CHECK (action IN ('INSERT','UPDATE','DELETE')),
  table_name  TEXT NOT NULL,
  row_pk      TEXT,
  old_data    JSONB,
  new_data    JSONB
);

CREATE INDEX IF NOT EXISTS idx_audit_log_time  ON audit_log(event_time);
CREATE INDEX IF NOT EXISTS idx_audit_log_table ON audit_log(table_name);


-- ---------------------------------------------------------
-- C) Fonctions génériques (updated_at + audit)
-- ---------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at := NOW();
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION fn_audit_generic()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  v_pk TEXT;
  j_old JSONB;
  j_new JSONB;
BEGIN
  IF TG_OP IN ('UPDATE','DELETE') THEN
    j_old := to_jsonb(OLD);
  END IF;
  IF TG_OP IN ('INSERT','UPDATE') THEN
    j_new := to_jsonb(NEW);
  END IF;

  -- récupérer un identifiant "id_*" existant
  v_pk := COALESCE(
    (COALESCE(j_new, j_old)->>'id_memoire'),
    (COALESCE(j_new, j_old)->>'id_soutenance'),
    (COALESCE(j_new, j_old)->>'id_note'),
    (COALESCE(j_new, j_old)->>'id_etudiant'),
    (COALESCE(j_new, j_old)->>'id_responsable'),
    (COALESCE(j_new, j_old)->>'id_jury'),
    (COALESCE(j_new, j_old)->>'id_departement'),
    (COALESCE(j_new, j_old)->>'id_niveau'),
    (COALESCE(j_new, j_old)->>'id_annee'),
    (COALESCE(j_new, j_old)->>'id_role'),
    (COALESCE(j_new, j_old)->>'id_salle')
  );

  INSERT INTO audit_log(action, table_name, row_pk, old_data, new_data)
  VALUES (TG_OP, TG_TABLE_NAME, v_pk, j_old, j_new);

  RETURN COALESCE(NEW, OLD);
END;
$$;


-- ---------------------------------------------------------
-- D) Activation des triggers génériques (idempotent)
-- ---------------------------------------------------------
DO $$
BEGIN
  -- updated_at
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_etudiant_updated_at') THEN
    CREATE TRIGGER trg_etudiant_updated_at
    BEFORE UPDATE ON etudiant
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_responsable_updated_at') THEN
    CREATE TRIGGER trg_responsable_updated_at
    BEFORE UPDATE ON responsable
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_memoire_updated_at') THEN
    CREATE TRIGGER trg_memoire_updated_at
    BEFORE UPDATE ON memoire
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_soutenance_updated_at') THEN
    CREATE TRIGGER trg_soutenance_updated_at
    BEFORE UPDATE ON soutenance
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_note_updated_at') THEN
    CREATE TRIGGER trg_note_updated_at
    BEFORE UPDATE ON note
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
  END IF;

  -- Optionnels (si tu gardes les colonnes techniques ci-dessus)
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_role_updated_at') THEN
    CREATE TRIGGER trg_role_updated_at
    BEFORE UPDATE ON role
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_jury_updated_at') THEN
    CREATE TRIGGER trg_jury_updated_at
    BEFORE UPDATE ON jury
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_encadrement_updated_at') THEN
    CREATE TRIGGER trg_encadrement_updated_at
    BEFORE UPDATE ON encadrement
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_composition_jury_updated_at') THEN
    CREATE TRIGGER trg_composition_jury_updated_at
    BEFORE UPDATE ON composition_jury
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
  END IF;

  -- audit (sur tables critiques)
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_audit_memoire') THEN
    CREATE TRIGGER trg_audit_memoire
    AFTER INSERT OR UPDATE OR DELETE ON memoire
    FOR EACH ROW EXECUTE FUNCTION fn_audit_generic();
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_audit_soutenance') THEN
    CREATE TRIGGER trg_audit_soutenance
    AFTER INSERT OR UPDATE OR DELETE ON soutenance
    FOR EACH ROW EXECUTE FUNCTION fn_audit_generic();
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_audit_note') THEN
    CREATE TRIGGER trg_audit_note
    AFTER INSERT OR UPDATE OR DELETE ON note
    FOR EACH ROW EXECUTE FUNCTION fn_audit_generic();
  END IF;
END $$;


-- =========================================================
-- E) RÈGLES MÉTIER (triggers “intelligents”)
-- =========================================================

-- E1) Transitions de statut mémoire (contrôle)
CREATE OR REPLACE FUNCTION fn_check_memoire_status_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  IF TG_OP = 'UPDATE' AND NEW.statut <> OLD.statut THEN
    IF OLD.statut = 'DEPOSE' AND NEW.statut IN ('EN_VERIFICATION') THEN
      RETURN NEW;
    ELSIF OLD.statut = 'EN_VERIFICATION' AND NEW.statut IN ('VALIDE','REFUSE') THEN
      RETURN NEW;
    ELSIF OLD.statut = 'REFUSE' AND NEW.statut IN ('EN_VERIFICATION') THEN
      RETURN NEW;
    ELSIF OLD.statut = 'VALIDE' THEN
      RAISE EXCEPTION 'Transition interdite: un mémoire VALIDE ne peut plus changer de statut.';
    ELSE
      RAISE EXCEPTION 'Transition statut mémoire interdite: % -> %', OLD.statut, NEW.statut;
    END IF;
  END IF;

  RETURN NEW;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_memoire_status_transition') THEN
    CREATE TRIGGER trg_memoire_status_transition
    BEFORE UPDATE ON memoire
    FOR EACH ROW EXECUTE FUNCTION fn_check_memoire_status_transition();
  END IF;
END $$;


-- E2) Empêcher planification soutenance si mémoire non VALIDE
CREATE OR REPLACE FUNCTION fn_soutenance_requires_memoire_valide()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  v_statut TEXT;
BEGIN
  SELECT statut INTO v_statut
  FROM memoire
  WHERE id_memoire = NEW.id_memoire;

  IF v_statut IS NULL THEN
    RAISE EXCEPTION 'Mémoire introuvable (id_memoire=%).', NEW.id_memoire;
  END IF;

  IF v_statut <> 'VALIDE' THEN
    RAISE EXCEPTION 'Impossible de planifier une soutenance: mémoire non VALIDE (statut=%).', v_statut;
  END IF;

  RETURN NEW;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_soutenance_requires_memoire_valide') THEN
    CREATE TRIGGER trg_soutenance_requires_memoire_valide
    BEFORE INSERT OR UPDATE ON soutenance
    FOR EACH ROW EXECUTE FUNCTION fn_soutenance_requires_memoire_valide();
  END IF;
END $$;


-- E3) Conflit de salle/date/heure interdit (hors ANNULEE)
CREATE OR REPLACE FUNCTION fn_no_room_conflict()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  v_exists INT;
BEGIN
  SELECT COUNT(*) INTO v_exists
  FROM soutenance s
  WHERE s.id_salle = NEW.id_salle
    AND s.date_ = NEW.date_
    AND s.heure = NEW.heure
    AND s.statut <> 'ANNULEE'
    AND (TG_OP = 'INSERT' OR s.id_soutenance <> NEW.id_soutenance);

  IF v_exists > 0 THEN
    RAISE EXCEPTION 'Conflit: une soutenance existe déjà pour cette salle et ce créneau.';
  END IF;

  RETURN NEW;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_soutenance_no_room_conflict') THEN
    CREATE TRIGGER trg_soutenance_no_room_conflict
    BEFORE INSERT OR UPDATE ON soutenance
    FOR EACH ROW EXECUTE FUNCTION fn_no_room_conflict();
  END IF;
END $$;


-- E4) Cohérence statut soutenance vs temps
CREATE OR REPLACE FUNCTION fn_check_soutenance_datetime()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  v_dt TIMESTAMP;
BEGIN
  v_dt := (NEW.date_::timestamp + NEW.heure);

  IF NEW.statut = 'PLANIFIEE' AND v_dt <= NOW() THEN
    RAISE EXCEPTION 'Soutenance PLANIFIEE doit être dans le futur (date/heure invalide).';
  END IF;

  RETURN NEW;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_soutenance_datetime_check') THEN
    CREATE TRIGGER trg_soutenance_datetime_check
    BEFORE INSERT OR UPDATE ON soutenance
    FOR EACH ROW EXECUTE FUNCTION fn_check_soutenance_datetime();
  END IF;
END $$;


-- E5) Note seulement si soutenance EFFECTUEE
CREATE OR REPLACE FUNCTION fn_check_note_only_if_effectuee()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  v_statut TEXT;
BEGIN
  SELECT statut INTO v_statut
  FROM soutenance
  WHERE id_soutenance = NEW.id_soutenance;

  IF v_statut IS NULL THEN
    RAISE EXCEPTION 'Soutenance introuvable (id_soutenance=%).', NEW.id_soutenance;
  END IF;

  IF v_statut <> 'EFFECTUEE' THEN
    RAISE EXCEPTION 'Impossible de saisir une note: soutenance non EFFECTUEE (statut=%).', v_statut;
  END IF;

  RETURN NEW;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_note_only_if_effectuee') THEN
    CREATE TRIGGER trg_note_only_if_effectuee
    BEFORE INSERT OR UPDATE ON note
    FOR EACH ROW EXECUTE FUNCTION fn_check_note_only_if_effectuee();
  END IF;
END $$;


-- E6) Vérifier jury “valide” avant d’affecter à une soutenance
-- - au moins 3 membres
-- - au moins 1 PRESIDENT et 1 RAPPORTEUR (via table role)
CREATE OR REPLACE FUNCTION fn_check_jury_composition_for_soutenance()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  v_total INT;
  v_pres  INT;
  v_rap   INT;
BEGIN
  SELECT COUNT(*) INTO v_total
  FROM composition_jury
  WHERE id_jury = NEW.id_jury;

  SELECT COUNT(*) INTO v_pres
  FROM composition_jury cj
  JOIN responsable r ON r.id_responsable = cj.id_responsable
  JOIN role ro       ON ro.id_role = r.id_role
  WHERE cj.id_jury = NEW.id_jury
    AND ro.code = 'PRESIDENT';

  SELECT COUNT(*) INTO v_rap
  FROM composition_jury cj
  JOIN responsable r ON r.id_responsable = cj.id_responsable
  JOIN role ro       ON ro.id_role = r.id_role
  WHERE cj.id_jury = NEW.id_jury
    AND ro.code = 'RAPPORTEUR';

  IF v_total < 3 THEN
    RAISE EXCEPTION 'Jury invalide: il faut au moins 3 membres (actuel=%).', v_total;
  END IF;

  IF v_pres < 1 THEN
    RAISE EXCEPTION 'Jury invalide: il faut au moins 1 PRESIDENT.';
  END IF;

  IF v_rap < 1 THEN
    RAISE EXCEPTION 'Jury invalide: il faut au moins 1 RAPPORTEUR.';
  END IF;

  RETURN NEW;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_soutenance_check_jury') THEN
    CREATE TRIGGER trg_soutenance_check_jury
    BEFORE INSERT OR UPDATE ON soutenance
    FOR EACH ROW EXECUTE FUNCTION fn_check_jury_composition_for_soutenance();
  END IF;
END $$;


-- E7) Neutralité: encadrant du mémoire ≠ membre du jury de ce mémoire
CREATE OR REPLACE FUNCTION fn_no_conflict_encadrant_in_jury()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  v_cnt INT;
BEGIN
  SELECT COUNT(*) INTO v_cnt
  FROM composition_jury cj
  JOIN encadrement e
    ON e.id_responsable = cj.id_responsable
  WHERE cj.id_jury = NEW.id_jury
    AND e.id_memoire = NEW.id_memoire;

  IF v_cnt > 0 THEN
    RAISE EXCEPTION 'Conflit: un encadrant du mémoire ne peut pas être membre du jury de ce mémoire.';
  END IF;

  RETURN NEW;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_soutenance_no_encadrant_in_jury') THEN
    CREATE TRIGGER trg_soutenance_no_encadrant_in_jury
    BEFORE INSERT OR UPDATE ON soutenance
    FOR EACH ROW EXECUTE FUNCTION fn_no_conflict_encadrant_in_jury();
  END IF;
END $$;


-- E8) Un mémoire doit avoir au moins 1 encadrant (contrôle après modif encadrement)
CREATE OR REPLACE FUNCTION fn_check_memoire_has_encadrant(p_id_memoire BIGINT)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_cnt INT;
BEGIN
  SELECT COUNT(*) INTO v_cnt
  FROM encadrement
  WHERE id_memoire = p_id_memoire;

  IF v_cnt < 1 THEN
    RAISE EXCEPTION 'Règle métier: un mémoire doit avoir au moins 1 encadrant (id_memoire=%).', p_id_memoire;
  END IF;
END;
$$;

CREATE OR REPLACE FUNCTION fn_check_memoire_has_encadrant_trg()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  v_memoire BIGINT;
BEGIN
  v_memoire := COALESCE(NEW.id_memoire, OLD.id_memoire);
  PERFORM fn_check_memoire_has_encadrant(v_memoire);
  RETURN COALESCE(NEW, OLD);
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_encadrement_requires_at_least_one') THEN
    CREATE TRIGGER trg_encadrement_requires_at_least_one
    AFTER INSERT OR UPDATE OR DELETE ON encadrement
    FOR EACH ROW EXECUTE FUNCTION fn_check_memoire_has_encadrant_trg();
  END IF;
END $$;

COMMIT;
