USE symptom_doctor_finder;

-- Q1. Display doctors with their specialization
SELECT
    d.doctor_id,
    d.name AS doctor_name,
    s.name AS specialization
FROM doctor d
JOIN specialization s
    ON d.specialization_id = s.specialization_id;


-- Q2. Display doctors with their clinic
SELECT
    d.doctor_id,
    d.name AS doctor_name,
    c.name AS clinic_name
FROM doctor d
JOIN clinic c
    ON d.clinic_id = c.clinic_id;


-- Q3. Display doctors with both clinic and specialization
SELECT
    d.doctor_id,
    d.name AS doctor_name,
    c.name AS clinic_name,
    s.name AS specialization
FROM doctor d
JOIN clinic c
    ON d.clinic_id = c.clinic_id
JOIN specialization s
    ON d.specialization_id = s.specialization_id;


-- Q4. Display appointments with patient names
SELECT
    a.appointment_id,
    p.name AS patient_name,
    a.status,
    a.booked_at
FROM appointment a
JOIN patient p
    ON a.patient_id = p.patient_id;


-- Q5. Display appointment details with patient and doctor
SELECT
    a.appointment_id,
    p.name AS patient_name,
    d.name AS doctor_name,
    a.status
FROM appointment a
JOIN patient p
    ON a.patient_id = p.patient_id
JOIN appointment_slot sl
    ON a.slot_id = sl.slot_id
JOIN doctor d
    ON sl.doctor_id = d.doctor_id;


-- Q6. Display complete appointment schedule
SELECT
    a.appointment_id,
    p.name AS patient_name,
    d.name AS doctor_name,
    s.name AS specialization,
    c.name AS clinic_name,
    sl.slot_date,
    sl.start_time,
    sl.end_time,
    a.status
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


-- Q7. Display completed consultations with patient and doctor
SELECT
    co.consultation_id,
    p.name AS patient_name,
    d.name AS doctor_name,
    co.diagnosis,
    co.consultation_date
FROM consultation co
JOIN appointment a
    ON co.appointment_id = a.appointment_id
JOIN patient p
    ON a.patient_id = p.patient_id
JOIN appointment_slot sl
    ON a.slot_id = sl.slot_id
JOIN doctor d
    ON sl.doctor_id = d.doctor_id;


-- Q8. Display prescriptions with patient and doctor
SELECT
    pr.prescription_id,
    p.name AS patient_name,
    d.name AS doctor_name,
    pr.medicine_name,
    pr.dosage,
    pr.duration
FROM prescription pr
JOIN consultation co
    ON pr.consultation_id = co.consultation_id
JOIN appointment a
    ON co.appointment_id = a.appointment_id
JOIN patient p
    ON a.patient_id = p.patient_id
JOIN appointment_slot sl
    ON a.slot_id = sl.slot_id
JOIN doctor d
    ON sl.doctor_id = d.doctor_id;


-- Q9. Display natural-language searches with their matched
-- specializations and similarity scores
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
    ON sspec.specialization_id = s.specialization_id
ORDER BY ss.search_id, sspec.similarity_score DESC;


-- Q10. Display semantic-search results with doctor information
SELECT
    ss.search_id,
    p.name AS patient_name,
    ss.symptom_text,
    s.name AS specialization,
    d.name AS doctor_name,
    sspec.similarity_score
FROM symptom_search ss
JOIN patient p
    ON ss.patient_id = p.patient_id
JOIN symptom_specialization sspec
    ON ss.search_id = sspec.search_id
JOIN specialization s
    ON sspec.specialization_id = s.specialization_id
JOIN doctor d
    ON d.specialization_id = s.specialization_id
ORDER BY ss.search_id, sspec.similarity_score DESC;