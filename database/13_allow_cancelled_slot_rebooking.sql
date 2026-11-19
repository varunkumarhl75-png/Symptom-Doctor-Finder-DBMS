USE symptom_doctor_finder;

-- This one-time migration uses a temporary stored procedure because MySQL
-- scripts cannot conditionally run DDL or SIGNAL from top-level SQL.
--
-- Before running:
--   1. Take and verify a schema-and-data backup.
--   2. Stop application writes to appointment until the migration is verified.
--   3. Confirm the helper routine name below is not already present:
--        SHOW PROCEDURE STATUS
--        WHERE Db = 'symptom_doctor_finder'
--          AND Name = 'migration_13_allow_cancelled_slot_rebooking_guard';
--      If it exists, stop and inspect it; do not overwrite or drop it blindly.
--   4. Execute this script without a client option that continues after errors.
--
-- The ALTER is a DDL statement with an implicit commit. It is not part of a
-- rollbackable transaction. Do not treat this migration as safely reversible.

DELIMITER $$

CREATE PROCEDURE migration_13_allow_cancelled_slot_rebooking_guard()
BEGIN
    DECLARE v_database VARCHAR(64);
    DECLARE v_table_count INT DEFAULT 0;
    DECLARE v_active_column_count INT DEFAULT 0;
    DECLARE v_active_column_valid INT DEFAULT 0;
    DECLARE v_old_index_count INT DEFAULT 0;
    DECLARE v_old_index_valid INT DEFAULT 0;
    DECLARE v_old_index_non_unique INT DEFAULT NULL;
    DECLARE v_old_index_column VARCHAR(64) DEFAULT NULL;
    DECLARE v_old_index_seq INT DEFAULT NULL;
    DECLARE v_old_index_sub_part BIGINT DEFAULT NULL;
    DECLARE v_new_index_count INT DEFAULT 0;
    DECLARE v_new_index_valid INT DEFAULT 0;
    DECLARE v_new_index_non_unique INT DEFAULT NULL;
    DECLARE v_new_index_column VARCHAR(64) DEFAULT NULL;
    DECLARE v_new_index_seq INT DEFAULT NULL;
    DECLARE v_new_index_sub_part BIGINT DEFAULT NULL;
    DECLARE v_slot_index_count INT DEFAULT 0;
    DECLARE v_slot_index_valid INT DEFAULT 0;
    DECLARE v_slot_index_non_unique INT DEFAULT NULL;
    DECLARE v_slot_index_column VARCHAR(64) DEFAULT NULL;
    DECLARE v_slot_index_seq INT DEFAULT NULL;
    DECLARE v_slot_index_sub_part BIGINT DEFAULT NULL;
    DECLARE v_slot_fk_count INT DEFAULT 0;
    DECLARE v_slot_fk_actions_valid INT DEFAULT 0;
    DECLARE v_patient_fk_count INT DEFAULT 0;
    DECLARE v_consultation_fk_count INT DEFAULT 0;
    DECLARE v_unique_index_count INT DEFAULT 0;
    DECLARE v_duplicate_active_groups INT DEFAULT 0;
    DECLARE v_rows_before BIGINT DEFAULT 0;
    DECLARE v_booked_before BIGINT DEFAULT 0;
    DECLARE v_completed_before BIGINT DEFAULT 0;
    DECLARE v_cancelled_before BIGINT DEFAULT 0;
    DECLARE v_rows_after BIGINT DEFAULT 0;
    DECLARE v_booked_after BIGINT DEFAULT 0;
    DECLARE v_completed_after BIGINT DEFAULT 0;
    DECLARE v_cancelled_after BIGINT DEFAULT 0;
    DECLARE v_statement_prepared BOOLEAN DEFAULT FALSE;
    DECLARE v_patient_fk_dropped BOOLEAN DEFAULT FALSE;
    DECLARE v_slot_fk_dropped BOOLEAN DEFAULT FALSE;
    DECLARE v_consultation_fk_dropped BOOLEAN DEFAULT FALSE;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        IF v_statement_prepared THEN
            DEALLOCATE PREPARE sdf_rebooking_alter;
        END IF;
        IF v_patient_fk_dropped THEN
            ALTER TABLE appointment
                ADD CONSTRAINT fk_appointment_patient
                FOREIGN KEY (patient_id)
                REFERENCES patient(patient_id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT;
        END IF;
        IF v_slot_fk_dropped THEN
            ALTER TABLE appointment
                ADD CONSTRAINT fk_appointment_slot
                FOREIGN KEY (slot_id)
                REFERENCES appointment_slot(slot_id)
                ON UPDATE RESTRICT
                ON DELETE RESTRICT;
        END IF;
        IF v_consultation_fk_dropped THEN
            ALTER TABLE consultation
                ADD CONSTRAINT fk_consultation_appointment
                FOREIGN KEY (appointment_id)
                REFERENCES appointment(appointment_id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT;
        END IF;
        RESIGNAL;
    END;

    SET v_database = DATABASE();
    IF v_database <> 'symptom_doctor_finder' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Wrong database selected; migration stopped.';
    END IF;

    SELECT COUNT(*)
      INTO v_table_count
      FROM information_schema.tables
     WHERE table_schema = v_database
       AND table_name = 'appointment'
       AND table_type = 'BASE TABLE';

    IF v_table_count <> 1 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'appointment table missing or unexpected; migration stopped.';
    END IF;

    SELECT COUNT(*)
      INTO v_active_column_count
      FROM information_schema.columns
     WHERE table_schema = v_database
       AND table_name = 'appointment'
       AND column_name = 'active_slot_id';

    SELECT COUNT(*)
      INTO v_active_column_valid
      FROM information_schema.columns
     WHERE table_schema = v_database
       AND table_name = 'appointment'
       AND column_name = 'active_slot_id'
       AND data_type = 'int'
       AND is_nullable = 'YES'
       AND extra LIKE '%GENERATED%'
       AND LOWER(REPLACE(generation_expression, CHAR(92), ''))
           LIKE '%case%when%status%cancelled%then%null%else%slot_id%end%';

    SELECT COUNT(*),
           MIN(non_unique),
           MAX(column_name),
           MAX(seq_in_index),
           MAX(sub_part)
      INTO v_old_index_count,
           v_old_index_non_unique,
           v_old_index_column,
           v_old_index_seq,
           v_old_index_sub_part
      FROM information_schema.statistics
     WHERE table_schema = v_database
       AND table_name = 'appointment'
       AND index_name = 'uq_appointment_slot';

    SELECT COUNT(*)
      INTO v_old_index_valid
      FROM information_schema.statistics
     WHERE table_schema = v_database
       AND table_name = 'appointment'
       AND index_name = 'uq_appointment_slot'
       AND non_unique = 0
       AND column_name = 'slot_id'
       AND seq_in_index = 1;

    SELECT COUNT(*),
           MIN(non_unique),
           MAX(column_name),
           MAX(seq_in_index),
           MAX(sub_part)
      INTO v_new_index_count,
           v_new_index_non_unique,
           v_new_index_column,
           v_new_index_seq,
           v_new_index_sub_part
      FROM information_schema.statistics
     WHERE table_schema = v_database
       AND table_name = 'appointment'
       AND index_name = 'uq_appointment_active_slot';

    SELECT COUNT(*)
      INTO v_new_index_valid
      FROM information_schema.statistics
     WHERE table_schema = v_database
       AND table_name = 'appointment'
       AND index_name = 'uq_appointment_active_slot'
       AND non_unique = 0
       AND column_name = 'active_slot_id'
       AND seq_in_index = 1;

    SELECT COUNT(*),
           MIN(non_unique),
           MAX(column_name),
           MAX(seq_in_index),
           MAX(sub_part)
      INTO v_slot_index_count,
           v_slot_index_non_unique,
           v_slot_index_column,
           v_slot_index_seq,
           v_slot_index_sub_part
      FROM information_schema.statistics
     WHERE table_schema = v_database
       AND table_name = 'appointment'
       AND index_name = 'idx_appointment_slot';

    SELECT COUNT(*)
      INTO v_slot_index_valid
      FROM information_schema.statistics
     WHERE table_schema = v_database
       AND table_name = 'appointment'
       AND index_name = 'idx_appointment_slot'
       AND non_unique = 1
       AND column_name = 'slot_id'
       AND seq_in_index = 1;

    SELECT COUNT(*)
      INTO v_slot_fk_count
      FROM information_schema.key_column_usage
     WHERE constraint_schema = v_database
       AND table_name = 'appointment'
       AND constraint_name = 'fk_appointment_slot'
       AND column_name = 'slot_id'
       AND referenced_table_name = 'appointment_slot'
       AND referenced_column_name = 'slot_id';

    SELECT COUNT(*)
      INTO v_patient_fk_count
      FROM information_schema.key_column_usage
     WHERE constraint_schema = v_database
       AND table_name = 'appointment'
       AND constraint_name = 'fk_appointment_patient'
       AND column_name = 'patient_id'
       AND referenced_table_name = 'patient'
       AND referenced_column_name = 'patient_id';

    SELECT COUNT(*)
      INTO v_consultation_fk_count
      FROM information_schema.key_column_usage
     WHERE constraint_schema = v_database
       AND table_name = 'consultation'
       AND constraint_name = 'fk_consultation_appointment'
       AND column_name = 'appointment_id'
       AND referenced_table_name = 'appointment'
       AND referenced_column_name = 'appointment_id';

    SELECT COUNT(*)
      INTO v_slot_fk_actions_valid
      FROM information_schema.referential_constraints
     WHERE constraint_schema = v_database
       AND table_name = 'appointment'
       AND constraint_name = 'fk_appointment_slot'
       AND update_rule = 'RESTRICT'
       AND delete_rule = 'RESTRICT';

    SELECT COUNT(DISTINCT index_name)
      INTO v_unique_index_count
      FROM information_schema.statistics
     WHERE table_schema = v_database
       AND table_name = 'appointment'
       AND non_unique = 0
       AND index_name <> 'PRIMARY';

    -- Reject same-named indexes with extra columns or a non-unique definition.
    IF v_old_index_count > 0
       AND (
           v_old_index_count <> 1
           OR v_old_index_valid <> 1
           OR v_old_index_non_unique <> 0
           OR v_old_index_column <> 'slot_id'
           OR v_old_index_seq <> 1
           OR v_old_index_sub_part IS NOT NULL
       ) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'uq_appointment_slot has an unexpected definition; manual review required.';
    END IF;

    IF v_new_index_count > 0
       AND (
           v_new_index_count <> 1
           OR v_new_index_valid <> 1
           OR v_new_index_non_unique <> 0
           OR v_new_index_column <> 'active_slot_id'
           OR v_new_index_seq <> 1
           OR v_new_index_sub_part IS NOT NULL
       ) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'uq_appointment_active_slot has an unexpected definition; manual review required.';
    END IF;

    IF v_slot_index_count > 0
       AND (
           v_slot_index_count <> 1
           OR v_slot_index_valid <> 1
           OR v_slot_index_non_unique <> 1
           OR v_slot_index_column <> 'slot_id'
           OR v_slot_index_seq <> 1
           OR v_slot_index_sub_part IS NOT NULL
       ) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'idx_appointment_slot has an unexpected definition; manual review required.';
    END IF;

    -- Already migrated: safe no-op only when the generated column and unique
    -- index match the intended definitions and the old index is absent.
    IF v_old_index_count = 0
       AND v_active_column_count = 1
       AND v_active_column_valid = 1
       AND v_new_index_count = 1
       AND v_new_index_valid = 1
       AND v_slot_index_count = 1
       AND v_slot_index_valid = 1
       AND v_slot_fk_count = 1
       AND v_slot_fk_actions_valid = 1
       AND v_patient_fk_count = 1
       AND v_consultation_fk_count = 1
       AND v_unique_index_count = 1 THEN
        SELECT 'Already migrated: no schema or data changes made.' AS migration_status;

    -- Original schema: old unique key only; no generated column or target key.
    ELSEIF v_old_index_count = 1
       AND v_old_index_valid = 1
       AND v_active_column_count = 0
       AND v_new_index_count = 0
       AND v_slot_fk_count = 1
       AND v_patient_fk_count = 1
       AND v_consultation_fk_count = 1
       AND v_unique_index_count = 1 THEN

        SELECT COUNT(*)
          INTO v_duplicate_active_groups
          FROM (
                SELECT slot_id
                  FROM appointment
                 WHERE status <> 'CANCELLED'
                 GROUP BY slot_id
                HAVING COUNT(*) > 1
          ) AS duplicate_active_slots;

        IF v_duplicate_active_groups > 0 THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Duplicate non-CANCELLED appointments found; migration stopped.';
        END IF;

        IF v_slot_index_count = 0 THEN
            ALTER TABLE appointment
                ADD INDEX idx_appointment_slot (slot_id);
        END IF;

        SELECT COUNT(*),
               COALESCE(SUM(status = 'BOOKED'), 0),
               COALESCE(SUM(status = 'COMPLETED'), 0),
               COALESCE(SUM(status = 'CANCELLED'), 0)
          INTO v_rows_before,
               v_booked_before,
               v_completed_before,
               v_cancelled_before
          FROM appointment;

        ALTER TABLE consultation
            DROP FOREIGN KEY fk_consultation_appointment;
        SET v_consultation_fk_dropped = TRUE;

        ALTER TABLE appointment
            DROP FOREIGN KEY fk_appointment_patient;
        SET v_patient_fk_dropped = TRUE;

        ALTER TABLE appointment
            DROP FOREIGN KEY fk_appointment_slot;
        SET v_slot_fk_dropped = TRUE;

        SET @sdf_rebooking_ddl =
            'ALTER TABLE appointment '
            'DROP INDEX uq_appointment_slot, '
            'ADD COLUMN active_slot_id INT '
            'GENERATED ALWAYS AS '
            '(CASE WHEN status = ''CANCELLED'' THEN NULL ELSE slot_id END) STORED, '
            'ADD UNIQUE KEY uq_appointment_active_slot (active_slot_id)';

        PREPARE sdf_rebooking_alter FROM @sdf_rebooking_ddl;
        SET v_statement_prepared = TRUE;
        EXECUTE sdf_rebooking_alter;
        DEALLOCATE PREPARE sdf_rebooking_alter;
        SET v_statement_prepared = FALSE;

        ALTER TABLE appointment
            ADD CONSTRAINT fk_appointment_patient
            FOREIGN KEY (patient_id)
            REFERENCES patient(patient_id)
            ON UPDATE CASCADE
            ON DELETE RESTRICT;
        SET v_patient_fk_dropped = FALSE;

        -- slot_id feeds active_slot_id, so a cascading key update is unsafe.
        ALTER TABLE appointment
            ADD CONSTRAINT fk_appointment_slot
            FOREIGN KEY (slot_id)
            REFERENCES appointment_slot(slot_id)
            ON UPDATE RESTRICT
            ON DELETE RESTRICT;
        SET v_slot_fk_dropped = FALSE;

        ALTER TABLE consultation
            ADD CONSTRAINT fk_consultation_appointment
            FOREIGN KEY (appointment_id)
            REFERENCES appointment(appointment_id)
            ON UPDATE CASCADE
            ON DELETE RESTRICT;
        SET v_consultation_fk_dropped = FALSE;

        SELECT COUNT(*)
          INTO v_active_column_valid
          FROM information_schema.columns
         WHERE table_schema = v_database
           AND table_name = 'appointment'
           AND column_name = 'active_slot_id'
           AND data_type = 'int'
           AND is_nullable = 'YES'
           AND extra LIKE '%GENERATED%'
           AND LOWER(REPLACE(generation_expression, CHAR(92), ''))
               LIKE '%case%when%status%cancelled%then%null%else%slot_id%end%';

        SELECT COUNT(*)
          INTO v_old_index_count
          FROM information_schema.statistics
         WHERE table_schema = v_database
           AND table_name = 'appointment'
           AND index_name = 'uq_appointment_slot';

        SELECT COUNT(*),
               MIN(non_unique),
               MAX(column_name),
               MAX(seq_in_index),
               MAX(sub_part)
          INTO v_new_index_count,
               v_new_index_non_unique,
               v_new_index_column,
               v_new_index_seq,
               v_new_index_sub_part
          FROM information_schema.statistics
         WHERE table_schema = v_database
           AND table_name = 'appointment'
           AND index_name = 'uq_appointment_active_slot';

        SELECT COUNT(*),
               MIN(non_unique),
               MAX(column_name),
               MAX(seq_in_index),
               MAX(sub_part)
          INTO v_slot_index_count,
               v_slot_index_non_unique,
               v_slot_index_column,
               v_slot_index_seq,
               v_slot_index_sub_part
          FROM information_schema.statistics
         WHERE table_schema = v_database
           AND table_name = 'appointment'
           AND index_name = 'idx_appointment_slot';

        SELECT COUNT(*)
          INTO v_slot_index_valid
          FROM information_schema.statistics
         WHERE table_schema = v_database
           AND table_name = 'appointment'
           AND index_name = 'idx_appointment_slot'
           AND non_unique = 1
           AND column_name = 'slot_id'
           AND seq_in_index = 1;

        SELECT COUNT(*)
          INTO v_slot_fk_count
          FROM information_schema.key_column_usage
         WHERE constraint_schema = v_database
           AND table_name = 'appointment'
           AND constraint_name = 'fk_appointment_slot'
           AND column_name = 'slot_id'
           AND referenced_table_name = 'appointment_slot'
           AND referenced_column_name = 'slot_id';

        SELECT COUNT(*)
          INTO v_patient_fk_count
          FROM information_schema.key_column_usage
         WHERE constraint_schema = v_database
           AND table_name = 'appointment'
           AND constraint_name = 'fk_appointment_patient'
           AND column_name = 'patient_id'
           AND referenced_table_name = 'patient'
           AND referenced_column_name = 'patient_id';

        SELECT COUNT(*)
          INTO v_consultation_fk_count
          FROM information_schema.key_column_usage
         WHERE constraint_schema = v_database
           AND table_name = 'consultation'
           AND constraint_name = 'fk_consultation_appointment'
           AND column_name = 'appointment_id'
           AND referenced_table_name = 'appointment'
           AND referenced_column_name = 'appointment_id';

        SELECT COUNT(*)
          INTO v_slot_fk_actions_valid
          FROM information_schema.referential_constraints
         WHERE constraint_schema = v_database
           AND table_name = 'appointment'
           AND constraint_name = 'fk_appointment_slot'
           AND update_rule = 'RESTRICT'
           AND delete_rule = 'RESTRICT';

        SELECT COUNT(DISTINCT index_name)
          INTO v_unique_index_count
          FROM information_schema.statistics
         WHERE table_schema = v_database
           AND table_name = 'appointment'
           AND non_unique = 0
           AND index_name <> 'PRIMARY';

        IF v_old_index_count <> 0
           OR v_active_column_valid <> 1
           OR v_new_index_count <> 1
           OR v_new_index_non_unique <> 0
           OR v_new_index_column <> 'active_slot_id'
           OR v_new_index_seq <> 1
           OR v_new_index_sub_part IS NOT NULL
           OR v_slot_index_count <> 1
           OR v_slot_index_valid <> 1
           OR v_slot_index_non_unique <> 1
           OR v_slot_index_column <> 'slot_id'
           OR v_slot_index_seq <> 1
           OR v_slot_index_sub_part IS NOT NULL
           OR v_slot_fk_count <> 1
           OR v_slot_fk_actions_valid <> 1
           OR v_patient_fk_count <> 1
           OR v_consultation_fk_count <> 1
           OR v_unique_index_count <> 1 THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Post-migration schema validation failed; inspect database immediately.';
        END IF;

        SELECT COUNT(*),
               COALESCE(SUM(status = 'BOOKED'), 0),
               COALESCE(SUM(status = 'COMPLETED'), 0),
               COALESCE(SUM(status = 'CANCELLED'), 0)
          INTO v_rows_after,
               v_booked_after,
               v_completed_after,
               v_cancelled_after
          FROM appointment;

        IF v_rows_after <> v_rows_before
           OR v_booked_after <> v_booked_before
           OR v_completed_after <> v_completed_before
           OR v_cancelled_after <> v_cancelled_before THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Appointment row/status counts changed during DDL; inspect database immediately.';
        END IF;

        SELECT COUNT(*)
          INTO v_duplicate_active_groups
          FROM (
                SELECT slot_id
                  FROM appointment
                 WHERE status <> 'CANCELLED'
                 GROUP BY slot_id
                HAVING COUNT(*) > 1
          ) AS duplicate_active_slots_after;

        IF v_duplicate_active_groups > 0 THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Post-migration active-slot validation failed; inspect database immediately.';
        END IF;

        SELECT 'Migration applied; verify schema and appointment counts before resuming writes.' AS migration_status;

    ELSE
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Unexpected or partially migrated schema; manual review required.';
    END IF;
END$$

DELIMITER ;

-- Execute only after confirming the helper routine name does not already exist.
CALL migration_13_allow_cancelled_slot_rebooking_guard();

-- Reached only if the CALL returned normally (applied or already migrated).
DROP PROCEDURE migration_13_allow_cancelled_slot_rebooking_guard;

-- If the client stops on an error, inspect the helper procedure before removing
-- it. Do not blindly rerun this script or drop an unverified routine.
