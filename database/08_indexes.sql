USE symptom_doctor_finder;

-- =========================================
-- INDEX 1: Patient email lookup
-- =========================================

CREATE INDEX idx_patient_email
ON patient(email);


-- =========================================
-- INDEX 2: Doctor specialization lookup
-- =========================================

CREATE INDEX idx_doctor_specialization
ON doctor(specialization_id);


-- =========================================
-- INDEX 3: Doctor clinic lookup
-- =========================================

CREATE INDEX idx_doctor_clinic
ON doctor(clinic_id);


-- =========================================
-- INDEX 4: Appointment status lookup
-- =========================================

CREATE INDEX idx_appointment_status
ON appointment(status);


-- =========================================
-- INDEX 5: Symptom search patient lookup
-- =========================================

CREATE INDEX idx_symptom_search_patient
ON symptom_search(patient_id);


-- =========================================
-- INDEX 6: Semantic-search specialization lookup
-- =========================================

CREATE INDEX idx_symptom_specialization
ON symptom_specialization(search_id, specialization_id);


-- =========================================
-- VERIFY INDEXES
-- =========================================

SHOW INDEX FROM patient;

SHOW INDEX FROM doctor;

SHOW INDEX FROM appointment;

SHOW INDEX FROM symptom_search;

SHOW INDEX FROM symptom_specialization;