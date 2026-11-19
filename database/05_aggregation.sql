USE symptom_doctor_finder;

-- Q1. Count total patients
SELECT COUNT(*) AS total_patients
FROM patient;


-- Q2. Count total doctors
SELECT COUNT(*) AS total_doctors
FROM doctor;


-- Q3. Count doctors in each specialization
SELECT
    s.name AS specialization,
    COUNT(d.doctor_id) AS doctor_count
FROM specialization s
LEFT JOIN doctor d
    ON s.specialization_id = d.specialization_id
GROUP BY s.specialization_id, s.name;


-- Q4. Count doctors in each clinic
SELECT
    c.name AS clinic_name,
    COUNT(d.doctor_id) AS doctor_count
FROM clinic c
LEFT JOIN doctor d
    ON c.clinic_id = d.clinic_id
GROUP BY c.clinic_id, c.name;


-- Q5. Average doctor experience
SELECT
    AVG(experience_years) AS average_experience
FROM doctor;


-- Q6. Maximum and minimum doctor experience
SELECT
    MAX(experience_years) AS maximum_experience,
    MIN(experience_years) AS minimum_experience
FROM doctor;


-- Q7. Average experience for each specialization
SELECT
    s.name AS specialization,
    AVG(d.experience_years) AS average_experience
FROM specialization s
JOIN doctor d
    ON s.specialization_id = d.specialization_id
GROUP BY s.specialization_id, s.name;


-- Q8. Count appointments by status
SELECT
    status,
    COUNT(*) AS appointment_count
FROM appointment
GROUP BY status;


-- Q9. Count appointments for each patient
SELECT
    p.patient_id,
    p.name AS patient_name,
    COUNT(a.appointment_id) AS appointment_count
FROM patient p
LEFT JOIN appointment a
    ON p.patient_id = a.patient_id
GROUP BY p.patient_id, p.name;


-- Q10. Specializations having more than one doctor
SELECT
    s.name AS specialization,
    COUNT(d.doctor_id) AS doctor_count
FROM specialization s
JOIN doctor d
    ON s.specialization_id = d.specialization_id
GROUP BY s.specialization_id, s.name
HAVING COUNT(d.doctor_id) > 1;


-- Q11. Clinics having at least two doctors
SELECT
    c.name AS clinic_name,
    COUNT(d.doctor_id) AS doctor_count
FROM clinic c
JOIN doctor d
    ON c.clinic_id = d.clinic_id
GROUP BY c.clinic_id, c.name
HAVING COUNT(d.doctor_id) >= 2;


-- Q12. Highest similarity score for each symptom search
SELECT
    ss.search_id,
    MAX(sspec.similarity_score) AS highest_similarity
FROM symptom_search ss
JOIN symptom_specialization sspec
    ON ss.search_id = sspec.search_id
GROUP BY ss.search_id;