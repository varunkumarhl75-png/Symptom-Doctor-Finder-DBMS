USE symptom_doctor_finder;

-- =========================================
-- PROCEDURE 1
-- Find doctors by specialization
-- =========================================

DROP PROCEDURE IF EXISTS get_doctors_by_specialization;

DELIMITER $$

CREATE PROCEDURE get_doctors_by_specialization(
    IN p_specialization_name VARCHAR(100)
)
SQL SECURITY INVOKER
BEGIN
    SELECT
        d.doctor_id,
        d.name AS doctor_name,
        s.name AS specialization,
        c.name AS clinic_name,
        d.qualification,
        d.experience_years,
        d.phone
    FROM doctor d
    JOIN specialization s
        ON d.specialization_id = s.specialization_id
    JOIN clinic c
        ON d.clinic_id = c.clinic_id
    WHERE s.name = p_specialization_name
    ORDER BY d.experience_years DESC;
END $$

DELIMITER ;


-- =========================================
-- PROCEDURE 2
-- Find available slots for a doctor
-- =========================================

DROP PROCEDURE IF EXISTS get_doctor_slots;

DELIMITER $$

CREATE PROCEDURE get_doctor_slots(
    IN p_doctor_id INT,
    IN p_date DATE
)
SQL SECURITY INVOKER
BEGIN
    SELECT
        sl.slot_id,
        d.name AS doctor_name,
        sl.slot_date,
        sl.start_time,
        sl.end_time
    FROM appointment_slot sl
    JOIN doctor d
        ON sl.doctor_id = d.doctor_id
    WHERE sl.doctor_id = p_doctor_id
      AND sl.slot_date = p_date
      AND TIMESTAMP(sl.slot_date, sl.start_time) > CURRENT_TIMESTAMP
      AND NOT EXISTS (
          SELECT 1
          FROM appointment a
          WHERE a.slot_id = sl.slot_id
            AND a.status <> 'CANCELLED'
      )
    ORDER BY sl.start_time;
END $$

DELIMITER ;


-- =========================================
-- PROCEDURE 3
-- Find experienced doctors
-- =========================================

DROP PROCEDURE IF EXISTS get_experienced_doctors;

DELIMITER $$

CREATE PROCEDURE get_experienced_doctors(
    IN p_min_experience INT
)
SQL SECURITY INVOKER
BEGIN
    SELECT
        d.doctor_id,
        d.name AS doctor_name,
        s.name AS specialization,
        d.experience_years
    FROM doctor d
    JOIN specialization s
        ON d.specialization_id = s.specialization_id
    WHERE d.experience_years >= p_min_experience
    ORDER BY d.experience_years DESC;
END $$

DELIMITER ;


-- =========================================
-- PROCEDURE 4
-- Get patient appointment history
-- =========================================

DROP PROCEDURE IF EXISTS get_patient_appointments;

DELIMITER $$

CREATE PROCEDURE get_patient_appointments(
    IN p_patient_id INT
)
SQL SECURITY INVOKER
BEGIN
    SELECT
        a.appointment_id,
        p.name AS patient_name,
        d.name AS doctor_name,
        s.name AS specialization,
        c.name AS clinic_name,
        sl.slot_date,
        sl.start_time,
        sl.end_time,
        a.status,
        a.notes
    FROM appointment a
    JOIN patient p
        ON a.patient_id = p.patient_id
    JOIN appointment_slot sl
        ON a.slot_id = sl.slot_id
    JOIN doctor d
        ON sl.doctor_id = d.doctor_id
    JOIN specialization s
        ON d.specialization_id = s.specialization_id
    JOIN clinic c
        ON d.clinic_id = c.clinic_id
    WHERE p.patient_id = p_patient_id
    ORDER BY sl.slot_date DESC, sl.start_time DESC;
END $$

DELIMITER ;