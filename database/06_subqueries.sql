USE symptom_doctor_finder;

-- Q1. Doctors having more experience than the overall average
SELECT
    doctor_id,
    name,
    experience_years
FROM doctor
WHERE experience_years >
      (SELECT AVG(experience_years)
       FROM doctor);


-- Q2. Patients who have at least one appointment
SELECT
    patient_id,
    name
FROM patient
WHERE patient_id IN
      (SELECT patient_id
       FROM appointment);


-- Q3. Doctors who work at clinics having more than one doctor
SELECT
    doctor_id,
    name,
    clinic_id
FROM doctor
WHERE clinic_id IN
      (
          SELECT clinic_id
          FROM doctor
          GROUP BY clinic_id
          HAVING COUNT(*) > 1
      );


-- Q4. Doctors belonging to the Cardiology specialization
SELECT
    doctor_id,
    name
FROM doctor
WHERE specialization_id =
      (
          SELECT specialization_id
          FROM specialization
          WHERE name = 'Cardiology'
      );


-- Q5. Patients who have completed appointments
SELECT
    patient_id,
    name
FROM patient
WHERE patient_id IN
      (
          SELECT patient_id
          FROM appointment
          WHERE status = 'COMPLETED'
      );


-- Q6. Doctors with experience greater than every doctor
-- in the General Medicine specialization
SELECT
    doctor_id,
    name,
    experience_years
FROM doctor
WHERE experience_years >
      (
          SELECT MAX(d2.experience_years)
          FROM doctor d2
          JOIN specialization s2
              ON d2.specialization_id = s2.specialization_id
          WHERE s2.name = 'General Medicine'
      );


-- Q7. Patients who have never booked an appointment
SELECT
    patient_id,
    name
FROM patient
WHERE patient_id NOT IN
      (
          SELECT patient_id
          FROM appointment
      );


-- Q8. Doctors who have at least one booked appointment
SELECT
    doctor_id,
    name
FROM doctor
WHERE doctor_id IN
      (
          SELECT sl.doctor_id
          FROM appointment_slot sl
          JOIN appointment a
              ON sl.slot_id = a.slot_id
          WHERE a.status = 'BOOKED'
      );


-- Q9. Search results whose similarity score is
-- greater than the average similarity score
SELECT
    search_id,
    specialization_id,
    similarity_score
FROM symptom_specialization
WHERE similarity_score >
      (
          SELECT AVG(similarity_score)
          FROM symptom_specialization
      );


-- Q10. Specializations having at least one doctor
SELECT
    specialization_id,
    name
FROM specialization s
WHERE EXISTS
      (
          SELECT 1
          FROM doctor d
          WHERE d.specialization_id = s.specialization_id
      );


-- =========================================
-- CORRELATED SUBQUERIES
-- =========================================

-- Q11. Doctors whose experience is greater than
-- the average experience in their own specialization
SELECT
    d1.doctor_id,
    d1.name,
    d1.specialization_id,
    d1.experience_years
FROM doctor d1
WHERE d1.experience_years >
      (
          SELECT AVG(d2.experience_years)
          FROM doctor d2
          WHERE d2.specialization_id = d1.specialization_id
      );


-- Q12. Highest similarity result for each search
-- using a correlated subquery
SELECT
    ss1.search_id,
    ss1.specialization_id,
    ss1.similarity_score
FROM symptom_specialization ss1
WHERE ss1.similarity_score =
      (
          SELECT MAX(ss2.similarity_score)
          FROM symptom_specialization ss2
          WHERE ss2.search_id = ss1.search_id
      );


-- Q13. Doctors who have at least one appointment
-- using EXISTS and a correlated subquery
SELECT
    d.doctor_id,
    d.name
FROM doctor d
WHERE EXISTS
      (
          SELECT 1
          FROM appointment_slot sl
          JOIN appointment a
              ON sl.slot_id = a.slot_id
          WHERE sl.doctor_id = d.doctor_id
      );