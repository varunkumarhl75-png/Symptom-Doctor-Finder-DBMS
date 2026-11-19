USE symptom_doctor_finder;

-- =========================================
-- 1. CLINICS
-- =========================================

INSERT INTO clinic (name, address, phone, email) VALUES
('City Care Hospital', 'MG Road, Bengaluru', '08040010001', 'contact@citycare.com'),
('Apollo Health Center', 'Koramangala, Bengaluru', '08040010002', 'contact@apollohealth.com'),
('Green Valley Clinic', 'Indiranagar, Bengaluru', '08040010003', 'info@greenvalley.com'),
('MediPlus Specialty Hospital', 'Whitefield, Bengaluru', '08040010004', 'info@mediplus.com'),
('Sunrise Medical Center', 'Jayanagar, Bengaluru', '08040010005', 'contact@sunrise.com');


-- =========================================
-- 2. SPECIALIZATIONS
-- =========================================

INSERT INTO specialization (name, description) VALUES
('Cardiology', 'Diagnosis and treatment of heart and cardiovascular conditions'),
('Neurology', 'Diagnosis and treatment of disorders of the brain and nervous system'),
('Dermatology', 'Diagnosis and treatment of skin, hair and nail conditions'),
('General Medicine', 'Primary diagnosis and treatment of common medical conditions'),
('Orthopedics', 'Treatment of bones, joints, muscles and related conditions'),
('Gynecology', 'Medical care related to the female reproductive system'),
('Pulmonology', 'Diagnosis and treatment of respiratory and lung conditions'),
('Nephrology', 'Diagnosis and treatment of kidney-related conditions');


-- =========================================
-- 3. PATIENTS
-- =========================================

INSERT INTO patient
(name, email, phone, date_of_birth, gender, address)
VALUES
('Rahul Sharma', 'rahul.sharma@email.com', '9876500001', '2002-05-14', 'Male', 'Bengaluru'),
('Priya Nair', 'priya.nair@email.com', '9876500002', '2001-08-22', 'Female', 'Bengaluru'),
('Arjun Kumar', 'arjun.kumar@email.com', '9876500003', '1999-11-10', 'Male', 'Mysuru'),
('Sneha Rao', 'sneha.rao@email.com', '9876500004', '2003-02-18', 'Female', 'Bengaluru'),
('Vikram Patel', 'vikram.patel@email.com', '9876500005', '1998-07-25', 'Male', 'Bengaluru'),
('Ananya Iyer', 'ananya.iyer@email.com', '9876500006', '2000-12-05', 'Female', 'Tumakuru'),
('Kiran Reddy', 'kiran.reddy@email.com', '9876500007', '1997-04-30', 'Male', 'Bengaluru'),
('Meera Joshi', 'meera.joshi@email.com', '9876500008', '2002-09-12', 'Female', 'Bengaluru'),
('Rohit Verma', 'rohit.verma@email.com', '9876500009', '1996-06-19', 'Male', 'Mangaluru'),
('Divya Menon', 'divya.menon@email.com', '9876500010', '2001-03-27', 'Female', 'Bengaluru');


-- =========================================
-- 4. DOCTORS
-- =========================================

INSERT INTO doctor
(clinic_id, specialization_id, name, email, phone, qualification, experience_years)
VALUES
(1, 1, 'Dr. Anil Mehta', 'anil.mehta@hospital.com', '9000000001', 'MD Cardiology', 12),
(2, 1, 'Dr. Kavya Rao', 'kavya.rao@hospital.com', '9000000002', 'DM Cardiology', 9),
(1, 2, 'Dr. Ramesh Iyer', 'ramesh.iyer@hospital.com', '9000000003', 'DM Neurology', 15),
(3, 2, 'Dr. Neha Singh', 'neha.singh@hospital.com', '9000000004', 'MD Neurology', 7),
(2, 3, 'Dr. Pooja Shah', 'pooja.shah@hospital.com', '9000000005', 'MD Dermatology', 8),
(3, 4, 'Dr. Suresh Kumar', 'suresh.kumar@hospital.com', '9000000006', 'MD General Medicine', 10),
(4, 5, 'Dr. Amit Joshi', 'amit.joshi@hospital.com', '9000000007', 'MS Orthopedics', 11),
(5, 6, 'Dr. Lakshmi Nair', 'lakshmi.nair@hospital.com', '9000000008', 'MD Gynecology', 13),
(4, 7, 'Dr. Farhan Ali', 'farhan.ali@hospital.com', '9000000009', 'MD Pulmonology', 9),
(5, 8, 'Dr. Swati Deshmukh', 'swati.deshmukh@hospital.com', '9000000010', 'DM Nephrology', 14),
(1, 4, 'Dr. Raj Malhotra', 'raj.malhotra@hospital.com', '9000000011', 'MD General Medicine', 6),
(2, 5, 'Dr. Nitin Rao', 'nitin.rao@hospital.com', '9000000012', 'MS Orthopedics', 8);


-- =========================================
-- 5. APPOINTMENT SLOTS
-- =========================================

INSERT INTO appointment_slot
(doctor_id, slot_date, start_time, end_time)
VALUES
(1, '2026-10-05', '09:00:00', '09:30:00'),
(1, '2026-10-05', '10:00:00', '10:30:00'),
(2, '2026-10-05', '11:00:00', '11:30:00'),
(3, '2026-10-05', '09:00:00', '09:30:00'),
(3, '2026-10-05', '10:00:00', '10:30:00'),
(4, '2026-10-06', '14:00:00', '14:30:00'),
(5, '2026-10-06', '10:00:00', '10:30:00'),
(6, '2026-10-06', '11:00:00', '11:30:00'),
(7, '2026-10-07', '09:30:00', '10:00:00'),
(8, '2026-10-07', '14:00:00', '14:30:00'),
(9, '2026-10-07', '15:00:00', '15:30:00'),
(10, '2026-10-08', '10:00:00', '10:30:00'),
(11, '2026-10-08', '11:00:00', '11:30:00'),
(12, '2026-10-08', '15:00:00', '15:30:00'),
(1, '2026-10-09', '09:00:00', '09:30:00'),
(3, '2026-10-09', '10:00:00', '10:30:00');


-- =========================================
-- 6. APPOINTMENTS
-- =========================================

INSERT INTO appointment
(patient_id, slot_id, status, notes)
VALUES
(1, 1, 'COMPLETED', 'Patient reported occasional chest discomfort'),
(2, 4, 'COMPLETED', 'Recurring headaches and dizziness'),
(3, 7, 'COMPLETED', 'Skin irritation and itching'),
(4, 8, 'BOOKED', 'General health consultation'),
(5, 9, 'BOOKED', 'Knee pain after physical activity'),
(6, 10, 'COMPLETED', 'Routine gynecological consultation'),
(7, 11, 'BOOKED', 'Breathing difficulty'),
(8, 12, 'BOOKED', 'Kidney-related consultation'),
(9, 13, 'CANCELLED', 'Appointment cancelled by patient'),
(10, 14, 'BOOKED', 'Joint pain consultation');


-- =========================================
-- 7. CONSULTATIONS
-- =========================================

INSERT INTO consultation
(appointment_id, diagnosis, notes, consultation_date, follow_up_date)
VALUES
(1, 'Mild cardiovascular symptoms', 'ECG recommended for further evaluation', '2026-10-05 09:45:00', '2026-10-19'),
(2, 'Migraine symptoms', 'Patient advised adequate hydration and rest', '2026-10-05 10:00:00', '2026-10-20'),
(3, 'Allergic dermatitis', 'Avoid identified skin irritants', '2026-10-06 10:45:00', '2026-10-20'),
(6, 'Routine examination', 'No immediate concerns identified', '2026-10-07 14:45:00', NULL);


-- =========================================
-- 8. PRESCRIPTIONS
-- =========================================

INSERT INTO prescription
(consultation_id, medicine_name, dosage, duration, instructions)
VALUES
(1, 'Aspirin', '75 mg', '5 days', 'Take after food'),
(1, 'Atorvastatin', '10 mg', '30 days', 'Take once daily at night'),
(2, 'Paracetamol', '500 mg', '3 days', 'Take when required for headache'),
(2, 'Propranolol', '20 mg', '14 days', 'Take as prescribed by doctor'),
(3, 'Cetirizine', '10 mg', '5 days', 'Take once daily'),
(3, 'Hydrocortisone Cream', 'Apply thin layer', '7 days', 'Apply to affected area'),
(4, 'Multivitamin', '1 tablet', '30 days', 'Take after breakfast');


-- =========================================
-- 9. NATURAL-LANGUAGE SYMPTOM SEARCHES
-- =========================================

INSERT INTO symptom_search
(patient_id, symptom_text)
VALUES
(1, 'I have been experiencing chest pain and shortness of breath when walking.'),
(2, 'I have severe headaches along with dizziness and occasional blurred vision.'),
(3, 'My skin has become red, itchy and irritated over the last few days.'),
(4, 'I have been feeling tired and weak with a mild fever.'),
(5, 'I have persistent pain around my knee after exercising.'),
(6, 'I need medical advice related to pregnancy and regular checkups.'),
(7, 'I am having difficulty breathing and feel tightness in my chest.'),
(8, 'I have pain in my lower back and some problems related to urination.'),
(9, 'I have recurring joint pain and stiffness in the morning.'),
(10, 'I have frequent headaches and difficulty concentrating.');


-- =========================================
-- 10. SEMANTIC SEARCH RESULTS
-- =========================================

INSERT INTO symptom_specialization
(search_id, specialization_id, similarity_score)
VALUES
-- Search 1: chest pain + breathing difficulty
(1, 1, 0.9412),
(1, 7, 0.8563),
(1, 4, 0.5124),

-- Search 2: headache + dizziness + blurred vision
(2, 2, 0.9325),
(2, 4, 0.5478),

-- Search 3: red + itchy skin
(3, 3, 0.9567),
(3, 4, 0.4912),

-- Search 4: tired + weak + fever
(4, 4, 0.9145),
(4, 2, 0.4123),

-- Search 5: knee pain
(5, 5, 0.9488),
(5, 4, 0.5061),

-- Search 6: pregnancy
(6, 6, 0.9734),
(6, 4, 0.4512),

-- Search 7: breathing difficulty + chest tightness
(7, 7, 0.9621),
(7, 1, 0.9014),

-- Search 8: lower back + urinary problems
(8, 8, 0.9256),
(8, 5, 0.4387),

-- Search 9: joint pain + stiffness
(9, 5, 0.9317),
(9, 4, 0.5128),

-- Search 10: headache + concentration problems
(10, 2, 0.8874),
(10, 4, 0.5362);