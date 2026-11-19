USE symptom_doctor_finder;

-- =========================================
-- TRIGGER 1
-- Prevent booking an already occupied slot
-- =========================================

DROP TRIGGER IF EXISTS before_appointment_insert;

DELIMITER $$

CREATE TRIGGER before_appointment_insert
BEFORE INSERT ON appointment
FOR EACH ROW
BEGIN
    IF EXISTS (
        SELECT 1
        FROM appointment_slot sl
        WHERE sl.slot_id = NEW.slot_id
          AND TIMESTAMP(sl.slot_date, sl.start_time) <= CURRENT_TIMESTAMP
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'This appointment slot has already passed';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM appointment
        WHERE slot_id = NEW.slot_id
          AND status <> 'CANCELLED'
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'This appointment slot is already occupied';
    END IF;
END $$

DELIMITER ;


-- =========================================
-- TRIGGER 2
-- Automatically set booked_at
-- =========================================

DROP TRIGGER IF EXISTS before_appointment_timestamp;

DELIMITER $$

CREATE TRIGGER before_appointment_timestamp
BEFORE INSERT ON appointment
FOR EACH ROW
BEGIN
    IF NEW.booked_at IS NULL THEN
        SET NEW.booked_at = CURRENT_TIMESTAMP;
    END IF;
END $$

DELIMITER ;


-- =========================================
-- TRIGGER 3
-- Prevent invalid doctor experience
-- =========================================

DROP TRIGGER IF EXISTS before_doctor_insert;

DELIMITER $$

CREATE TRIGGER before_doctor_insert
BEFORE INSERT ON doctor
FOR EACH ROW
BEGIN
    IF NEW.experience_years < 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Experience years cannot be negative';
    END IF;
END $$

DELIMITER ;