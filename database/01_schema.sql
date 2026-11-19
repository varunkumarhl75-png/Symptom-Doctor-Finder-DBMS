CREATE DATABASE IF NOT EXISTS symptom_doctor_finder;

USE symptom_doctor_finder;

-- =========================================
-- 1. PATIENT
-- =========================================

CREATE TABLE patient (
    patient_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    phone VARCHAR(15) NOT NULL,
    date_of_birth DATE,
    gender VARCHAR(20),
    address VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- =========================================
-- 2. CLINIC
-- =========================================

CREATE TABLE clinic (
    clinic_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    address VARCHAR(255) NOT NULL,
    phone VARCHAR(15),
    email VARCHAR(150)
);

-- =========================================
-- 3. SPECIALIZATION
-- =========================================

CREATE TABLE specialization (
    specialization_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT
);

-- =========================================
-- 4. DOCTOR
-- =========================================

CREATE TABLE doctor (
    doctor_id INT AUTO_INCREMENT PRIMARY KEY,
    clinic_id INT NOT NULL,
    specialization_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    phone VARCHAR(15) NOT NULL,
    qualification VARCHAR(150),
    experience_years INT,

    CONSTRAINT fk_doctor_clinic
        FOREIGN KEY (clinic_id)
        REFERENCES clinic(clinic_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_doctor_specialization
        FOREIGN KEY (specialization_id)
        REFERENCES specialization(specialization_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT chk_doctor_experience
        CHECK (experience_years >= 0)
);

-- =========================================
-- 5. APPOINTMENT SLOT
-- =========================================

CREATE TABLE appointment_slot (
    slot_id INT AUTO_INCREMENT PRIMARY KEY,
    doctor_id INT NOT NULL,
    slot_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,

    CONSTRAINT fk_slot_doctor
        FOREIGN KEY (doctor_id)
        REFERENCES doctor(doctor_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT chk_slot_time
        CHECK (end_time > start_time),

    CONSTRAINT uq_doctor_slot
        UNIQUE (doctor_id, slot_date, start_time, end_time)
);

-- =========================================
-- 6. APPOINTMENT
-- =========================================

CREATE TABLE appointment (
    appointment_id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    slot_id INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'BOOKED',
    active_slot_id INT
        GENERATED ALWAYS AS (
            CASE WHEN status = 'CANCELLED' THEN NULL ELSE slot_id END
        ) STORED,
    booked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,

    CONSTRAINT fk_appointment_patient
        FOREIGN KEY (patient_id)
        REFERENCES patient(patient_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_appointment_slot
        FOREIGN KEY (slot_id)
        REFERENCES appointment_slot(slot_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT chk_appointment_status
        CHECK (status IN ('BOOKED', 'COMPLETED', 'CANCELLED')),

    CONSTRAINT uq_appointment_active_slot
        UNIQUE (active_slot_id)
);

-- =========================================
-- 7. CONSULTATION
-- =========================================

CREATE TABLE consultation (
    consultation_id INT AUTO_INCREMENT PRIMARY KEY,
    appointment_id INT NOT NULL UNIQUE,
    diagnosis TEXT,
    notes TEXT,
    consultation_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    follow_up_date DATE,

    CONSTRAINT fk_consultation_appointment
        FOREIGN KEY (appointment_id)
        REFERENCES appointment(appointment_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

-- =========================================
-- 8. PRESCRIPTION
-- =========================================

CREATE TABLE prescription (
    prescription_id INT AUTO_INCREMENT PRIMARY KEY,
    consultation_id INT NOT NULL,
    medicine_name VARCHAR(150) NOT NULL,
    dosage VARCHAR(100),
    duration VARCHAR(100),
    instructions TEXT,

    CONSTRAINT fk_prescription_consultation
        FOREIGN KEY (consultation_id)
        REFERENCES consultation(consultation_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

-- =========================================
-- 9. SYMPTOM SEARCH
-- =========================================

CREATE TABLE symptom_search (
    search_id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    symptom_text TEXT NOT NULL,
    search_date DATETIME DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_search_patient
        FOREIGN KEY (patient_id)
        REFERENCES patient(patient_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

-- =========================================
-- 10. SYMPTOM SPECIALIZATION
-- =========================================

CREATE TABLE symptom_specialization (
    search_id INT NOT NULL,
    specialization_id INT NOT NULL,
    similarity_score DECIMAL(5,4) NOT NULL,

    PRIMARY KEY (search_id, specialization_id),

    CONSTRAINT fk_ss_search
        FOREIGN KEY (search_id)
        REFERENCES symptom_search(search_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT fk_ss_specialization
        FOREIGN KEY (specialization_id)
        REFERENCES specialization(specialization_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT chk_similarity_score
        CHECK (similarity_score >= 0 AND similarity_score <= 1)
);