USE symptom_doctor_finder;

-- Authentication accounts are separate from patient records. Registration
-- creates a new patient and linked PATIENT account in one transaction.
-- Existing patient rows are deliberately not auto-linked: email alone does
-- not prove that the registering person owns an older seeded patient record.
CREATE TABLE IF NOT EXISTS auth_user (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(10) NOT NULL,
    patient_id INT NULL UNIQUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_auth_user_patient
        FOREIGN KEY (patient_id)
        REFERENCES patient(patient_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT chk_auth_user_role
        CHECK (role IN ('PATIENT', 'ADMIN')),

    CONSTRAINT chk_auth_user_patient_link
        CHECK (
            (role = 'PATIENT' AND patient_id IS NOT NULL)
            OR (role = 'ADMIN' AND patient_id IS NULL)
        )
) ENGINE=InnoDB;

-- Dedicated, non-login definer for the public patient-registration routine.
-- Before reusing an existing account with this name, inspect SHOW GRANTS and
-- remove any unrelated grants/roles. The account should remain locked.
CREATE USER IF NOT EXISTS 'sdf_registration_definer'@'localhost' ACCOUNT LOCK;
ALTER USER 'sdf_registration_definer'@'localhost' ACCOUNT LOCK;

GRANT SELECT, INSERT ON symptom_doctor_finder.patient
    TO 'sdf_registration_definer'@'localhost';
GRANT SELECT, INSERT ON symptom_doctor_finder.auth_user
    TO 'sdf_registration_definer'@'localhost';

-- Reapplying this migration replaces the routine and may remove its EXECUTE
-- grants. Reapply database/16_mysql_rbac.sql afterward.
DROP PROCEDURE IF EXISTS register_patient_account;

DELIMITER $$

CREATE DEFINER = 'sdf_registration_definer'@'localhost'
PROCEDURE register_patient_account(
    IN p_name VARCHAR(100),
    IN p_email VARCHAR(150),
    IN p_phone VARCHAR(15),
    IN p_password_hash VARCHAR(255),
    OUT p_patient_id INT,
    OUT p_user_id INT
)
SQL SECURITY DEFINER
MODIFIES SQL DATA
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SET p_patient_id = NULL;
    SET p_user_id = NULL;

    START TRANSACTION;

    IF EXISTS (
        SELECT 1
        FROM patient
        WHERE email = p_email
    ) OR EXISTS (
        SELECT 1
        FROM auth_user
        WHERE email = p_email
    ) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Registration email already exists';
    END IF;

    INSERT INTO patient (name, email, phone)
    VALUES (p_name, p_email, p_phone);
    SET p_patient_id = LAST_INSERT_ID();

    INSERT INTO auth_user (email, password_hash, role, patient_id)
    VALUES (p_email, p_password_hash, 'PATIENT', p_patient_id);
    SET p_user_id = LAST_INSERT_ID();

    COMMIT;
END$$

DELIMITER ;
