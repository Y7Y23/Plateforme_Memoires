BEGIN;

SET search_path TO isms;

-- =========================================================
-- 1) CONVERSATION
-- =========================================================
CREATE TABLE IF NOT EXISTS conversation (
  id_conversation BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),

  id_etudiant BIGINT NOT NULL,
  id_responsable BIGINT NOT NULL,
  id_memoire BIGINT NOT NULL,

  CONSTRAINT fk_conv_etudiant
    FOREIGN KEY (id_etudiant) REFERENCES etudiant(id_etudiant)
    ON UPDATE CASCADE ON DELETE CASCADE,

  CONSTRAINT fk_conv_responsable
    FOREIGN KEY (id_responsable) REFERENCES responsable(id_responsable)
    ON UPDATE CASCADE ON DELETE CASCADE,

  CONSTRAINT fk_conv_memoire
    FOREIGN KEY (id_memoire) REFERENCES memoire(id_memoire)
    ON UPDATE CASCADE ON DELETE CASCADE
);

-- ✅ 1 conversation unique par (etudiant, responsable, memoire)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'uq_conversation_triplet'
      AND conrelid = 'isms.conversation'::regclass
  ) THEN
    ALTER TABLE isms.conversation
      ADD CONSTRAINT uq_conversation_triplet
      UNIQUE (id_etudiant, id_responsable, id_memoire);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_conversation_etudiant
  ON isms.conversation(id_etudiant);

CREATE INDEX IF NOT EXISTS idx_conversation_responsable
  ON isms.conversation(id_responsable);

CREATE INDEX IF NOT EXISTS idx_conversation_memoire
  ON isms.conversation(id_memoire);


-- =========================================================
-- 2) MESSAGE
-- =========================================================
CREATE TABLE IF NOT EXISTS message (
  id_message BIGSERIAL PRIMARY KEY,
  id_conversation BIGINT NOT NULL,

  sender_type VARCHAR(15) NOT NULL,  -- 'ETUDIANT' | 'RESPONSABLE'
  sender_id BIGINT NOT NULL,         -- id_etudiant ou id_responsable

  contenu TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  is_read BOOLEAN NOT NULL DEFAULT FALSE,

  CONSTRAINT fk_msg_conversation
    FOREIGN KEY (id_conversation) REFERENCES conversation(id_conversation)
    ON UPDATE CASCADE ON DELETE CASCADE,

  CONSTRAINT ck_sender_type
    CHECK (sender_type IN ('ETUDIANT','RESPONSABLE'))
);

CREATE INDEX IF NOT EXISTS idx_message_conversation_date
  ON isms.message(id_conversation, created_at);

CREATE INDEX IF NOT EXISTS idx_message_is_read
  ON isms.message(is_read);


-- =========================================================
-- 3) RÈGLES MÉTIER (triggers)
--    A) conversation doit être cohérente :
--       - memoire.id_etudiant = conversation.id_etudiant
--       - responsable doit être encadrant/co-encadrant de ce memoire
-- =========================================================
CREATE OR REPLACE FUNCTION isms.fn_check_conversation_valid()
RETURNS trigger AS $$
DECLARE
  v_ok INT;
BEGIN
  -- 1) le mémoire appartient bien à l'étudiant
  SELECT 1 INTO v_ok
  FROM isms.memoire m
  WHERE m.id_memoire = NEW.id_memoire
    AND m.id_etudiant = NEW.id_etudiant
  LIMIT 1;

  IF v_ok IS NULL THEN
    RAISE EXCEPTION 'Conversation invalide: ce mémoire n’appartient pas à cet étudiant (id_memoire=%).', NEW.id_memoire;
  END IF;

  -- 2) le responsable est bien encadrant ou co-encadrant du mémoire
  SELECT 1 INTO v_ok
  FROM isms.encadrement en
  WHERE en.id_memoire = NEW.id_memoire
    AND en.id_responsable = NEW.id_responsable
    AND en.encadrement IN ('ENCADRANT','CO_ENCADRANT')
  LIMIT 1;

  IF v_ok IS NULL THEN
    RAISE EXCEPTION 'Conversation invalide: ce responsable n’est pas encadrant/co-encadrant de ce mémoire.';
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conversation_check_valid ON isms.conversation;

CREATE TRIGGER trg_conversation_check_valid
BEFORE INSERT OR UPDATE ON isms.conversation
FOR EACH ROW
EXECUTE FUNCTION isms.fn_check_conversation_valid();


-- =========================================================
--    B) message doit être cohérent :
--       - si sender_type='ETUDIANT' => sender_id = conversation.id_etudiant
--       - si sender_type='RESPONSABLE' => sender_id = conversation.id_responsable
-- =========================================================
CREATE OR REPLACE FUNCTION isms.fn_check_message_sender()
RETURNS trigger AS $$
DECLARE
  v_etudiant BIGINT;
  v_responsable BIGINT;
BEGIN
  SELECT c.id_etudiant, c.id_responsable
    INTO v_etudiant, v_responsable
  FROM isms.conversation c
  WHERE c.id_conversation = NEW.id_conversation
  LIMIT 1;

  IF v_etudiant IS NULL THEN
    RAISE EXCEPTION 'Message invalide: conversation introuvable (id_conversation=%).', NEW.id_conversation;
  END IF;

  IF NEW.sender_type = 'ETUDIANT' AND NEW.sender_id <> v_etudiant THEN
    RAISE EXCEPTION 'Message invalide: sender_id ne correspond pas à l’étudiant de la conversation.';
  END IF;

  IF NEW.sender_type = 'RESPONSABLE' AND NEW.sender_id <> v_responsable THEN
    RAISE EXCEPTION 'Message invalide: sender_id ne correspond pas au responsable de la conversation.';
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_message_check_sender ON isms.message;

CREATE TRIGGER trg_message_check_sender
BEFORE INSERT ON isms.message
FOR EACH ROW
EXECUTE FUNCTION isms.fn_check_message_sender();

COMMIT;
