USE symptom_doctor_finder;

-- Q1. Display all patients
SELECT *
FROM patient;


-- Q2. Display only patient names and phone numbers
SELECT name, phone
FROM patient;


-- Q3. Find female patients
SELECT patient_id, name, email
FROM patient
WHERE gender = 'Female';


-- Q4. Find doctors with more than 10 years of experience
SELECT doctor_id, name, experience_years
FROM doctor
WHERE experience_years > 10;


-- Q5. Display doctors in alphabetical order
SELECT doctor_id, name, experience_years
FROM doctor
ORDER BY name ASC;


-- Q6. Display doctors from most experienced to least experienced
SELECT doctor_id, name, experience_years
FROM doctor
ORDER BY experience_years DESC;


-- Q7. Find patients whose names start with 'A'
SELECT patient_id, name
FROM patient
WHERE name LIKE 'A%';


-- Q8. Find doctors having between 8 and 12 years of experience
SELECT doctor_id, name, experience_years
FROM doctor
WHERE experience_years BETWEEN 8 AND 12;


-- Q9. Display unique patient genders
SELECT DISTINCT gender
FROM patient;


-- Q10. Find appointments that are currently booked
SELECT appointment_id, patient_id, slot_id, status
FROM appointment
WHERE status = 'BOOKED';


-- Q11. Display cancelled or completed appointments
SELECT appointment_id, patient_id, status
FROM appointment
WHERE status IN ('CANCELLED', 'COMPLETED');


-- Q12. Find natural-language searches containing the word 'pain'
SELECT search_id, patient_id, symptom_text
FROM symptom_search
WHERE symptom_text LIKE '%pain%';