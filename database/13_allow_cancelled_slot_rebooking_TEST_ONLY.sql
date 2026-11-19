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

        SELECT COUNT(DISTINCT index_name)
          INTO v_unique_index_count
          FROM information_schema.statistics
         WHERE table_schema = v_database
           AND table_name = 'appointment'
           AND non_unique = 0
           AND index_name <> 'PRIMARY';

        IF v_old_index_count <> 0
           OR v_active_column_valid <> 1
           OR v_slot_index_count <> 1
           OR v_slot_index_valid <> 1
           OR v_slot_index_non_unique <> 1
           OR v_slot_index_column <> 'slot_id'
           OR v_slot_index_seq <> 1
           OR v_slot_index_sub_part IS NOT NULL
           OR v_new_index_count <> 1
           OR v_new_index_valid <> 1
           OR v_new_index_non_unique <> 0
           OR v_new_index_column <> 'active_slot_id'
           OR v_new_index_seq <> 1
           OR v_new_index_sub_part IS NOT NULL
           OR v_unique_index_count <> 1 THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Post-migration schema validation failed; inspect database immediately.';
        END IF;

        -- Verify appointment rows and status counts did not change.
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

-- Execute only after confirming this helper routine does not already exist.
CALL migration_13_allow_cancelled_slot_rebooking_guard();

-- Reached only if the CALL returned normally (applied or already migrated).
DROP PROCEDURE migration_13_allow_cancelled_slot_rebooking_guard;
