USE symptom_doctor_finder;

-- =========================================
-- TRANSACTION 1: COMMIT
-- =========================================

START TRANSACTION;

INSERT INTO appointment
    (patient_id, slot_id, status, notes)
VALUES
    (2, 3, 'BOOKED', 'Transaction commit test');

COMMIT;

SELECT
    appointment_id,
    patient_id,
    slot_id,
    status,
    notes
FROM appointment
WHERE notes = 'Transaction commit test';

-- Clean up committed test data
DELETE FROM appointment
WHERE notes = 'Transaction commit test';


-- =========================================
-- TRANSACTION 2: ROLLBACK
-- =========================================

START TRANSACTION;

INSERT INTO appointment
    (patient_id, slot_id, status, notes)
VALUES
    (3, 5, 'BOOKED', 'Transaction rollback test');

ROLLBACK;

SELECT
    appointment_id,
    patient_id,
    slot_id,
    status,
    notes
FROM appointment
WHERE notes = 'Transaction rollback test';


-- =========================================
-- TRANSACTION 3: SAVEPOINT
-- =========================================

START TRANSACTION;

INSERT INTO appointment
    (patient_id, slot_id, status, notes)
VALUES
    (4, 3, 'BOOKED', 'Savepoint test 1');

SAVEPOINT appointment_savepoint;

INSERT INTO appointment
    (patient_id, slot_id, status, notes)
VALUES
    (5, 5, 'BOOKED', 'Savepoint test 2');

ROLLBACK TO appointment_savepoint;

COMMIT;

SELECT
    appointment_id,
    patient_id,
    slot_id,
    status,
    notes
FROM appointment
WHERE notes LIKE 'Savepoint test%';

-- Clean up savepoint test
DELETE FROM appointment
WHERE notes = 'Savepoint test 1';