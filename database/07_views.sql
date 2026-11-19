USE symptom_doctor_finder;

-- =========================================
-- VIEW 1: Doctor Directory
-- =========================================

CREATE OR REPLACE VIEW doctor_directory AS
SELECT
    d.doctor_id,
    d.name AS doctor_name,
    s.name AS specialization,
    c.name AS clinic_name,
    d.qualification,
    d.experience_years,
    d.phone,
    d.email
FROM doctor d
JOIN specialization s
    ON d.specialization_id = s.specialization_id
JOIN clinic c
    ON d.clinic_id = c.clinic_id;


-- =========================================
-- VIEW 2: Complete Appointment Details
-- =========================================

CREATE OR REPLACE VIEW appointment_details AS
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
    a.booked_at,
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
    ON d.clinic_id = c.clinic_id;


-- =========================================
-- VIEW 3: Semantic Search Results
-- =========================================

CREATE OR REPLACE VIEW semantic_search_results AS
SELECT
    ss.search_id,
    p.name AS patient_name,
    ss.symptom_text,
    s.name AS specialization,
    sspec.similarity_score
FROM symptom_search ss
JOIN patient p
    ON ss.patient_id = p.patient_id
JOIN symptom_specialization sspec
    ON ss.search_id = sspec.search_id
JOIN specialization s
    ON sspec.specialization_id = s.specialization_id;


-- =========================================
-- VIEW 4: Doctor Appointment Summary
-- =========================================

CREATE OR REPLACE VIEW doctor_appointment_summary AS
SELECT
    d.doctor_id,
    d.name AS doctor_name,
    s.name AS specialization,
    COUNT(a.appointment_id) AS total_appointments,
    SUM(
        CASE
            WHEN a.status = 'COMPLETED' THEN 1
            ELSE 0
        END
    ) AS completed_appointments,
    SUM(
        CASE
            WHEN a.status = 'BOOKED' THEN 1
            ELSE 0
        END
    ) AS booked_appointments,
    SUM(
        CASE
            WHEN a.status = 'CANCELLED' THEN 1
            ELSE 0
        END
    ) AS cancelled_appointments
FROM doctor d
JOIN specialization s
    ON d.specialization_id = s.specialization_id
LEFT JOIN appointment_slot sl
    ON d.doctor_id = sl.doctor_id
LEFT JOIN appointment a
    ON sl.slot_id = a.slot_id
GROUP BY
    d.doctor_id,
    d.name,
    s.name;