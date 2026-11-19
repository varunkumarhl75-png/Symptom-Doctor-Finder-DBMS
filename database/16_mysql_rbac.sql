USE symptom_doctor_finder;

-- Execute only after reviewing the account names and host restrictions.
-- MySQL generates random passwords; capture its output securely and configure
-- the generated sdf_app password as DB_PASSWORD in the local environment.
-- This script does not reset passwords for accounts that already exist.

CREATE ROLE IF NOT EXISTS 'sdf_app_role';

GRANT SELECT ON symptom_doctor_finder.clinic TO 'sdf_app_role';
GRANT SELECT ON symptom_doctor_finder.doctor TO 'sdf_app_role';
GRANT SELECT ON symptom_doctor_finder.specialization TO 'sdf_app_role';
GRANT SELECT ON symptom_doctor_finder.appointment_slot TO 'sdf_app_role';
GRANT SELECT ON symptom_doctor_finder.patient TO 'sdf_app_role';
GRANT SELECT, INSERT, UPDATE ON symptom_doctor_finder.appointment TO 'sdf_app_role';
GRANT SELECT ON symptom_doctor_finder.auth_user TO 'sdf_app_role';
GRANT SELECT ON symptom_doctor_finder.symptom_search TO 'sdf_app_role';
GRANT SELECT ON symptom_doctor_finder.symptom_specialization TO 'sdf_app_role';
GRANT EXECUTE ON PROCEDURE symptom_doctor_finder.register_patient_account TO 'sdf_app_role';
GRANT EXECUTE ON PROCEDURE symptom_doctor_finder.get_doctor_slots TO 'sdf_app_role';
GRANT EXECUTE ON PROCEDURE symptom_doctor_finder.get_patient_appointments TO 'sdf_app_role';

CREATE USER IF NOT EXISTS 'sdf_app'@'localhost' IDENTIFIED BY RANDOM PASSWORD;
GRANT 'sdf_app_role' TO 'sdf_app'@'localhost';
SET DEFAULT ROLE 'sdf_app_role' TO 'sdf_app'@'localhost';

-- This separate local database-maintenance account is not used by Flask.
-- It can maintain doctor/schedule catalog data but is not a MySQL superuser.
CREATE ROLE IF NOT EXISTS 'sdf_catalog_maintenance_role';
GRANT SELECT ON symptom_doctor_finder.clinic TO 'sdf_catalog_maintenance_role';
GRANT SELECT ON symptom_doctor_finder.doctor TO 'sdf_catalog_maintenance_role';
GRANT SELECT ON symptom_doctor_finder.specialization TO 'sdf_catalog_maintenance_role';
GRANT SELECT ON symptom_doctor_finder.appointment_slot TO 'sdf_catalog_maintenance_role';
GRANT INSERT, UPDATE, DELETE
    ON symptom_doctor_finder.clinic TO 'sdf_catalog_maintenance_role';
GRANT INSERT, UPDATE, DELETE
    ON symptom_doctor_finder.doctor TO 'sdf_catalog_maintenance_role';
GRANT INSERT, UPDATE, DELETE
    ON symptom_doctor_finder.specialization TO 'sdf_catalog_maintenance_role';
GRANT INSERT, UPDATE, DELETE
    ON symptom_doctor_finder.appointment_slot TO 'sdf_catalog_maintenance_role';

CREATE USER IF NOT EXISTS 'sdf_db_maintainer'@'localhost' IDENTIFIED BY RANDOM PASSWORD;
GRANT 'sdf_catalog_maintenance_role' TO 'sdf_db_maintainer'@'localhost';
SET DEFAULT ROLE 'sdf_catalog_maintenance_role' TO 'sdf_db_maintainer'@'localhost';

-- A separate trusted principal used only by app/create_admin.py. This account
-- can inspect existing admin rows and create an auth_user row, but cannot log
-- into Flask or modify patient, appointment, or catalog records.
CREATE ROLE IF NOT EXISTS 'sdf_admin_creator_role';
GRANT SELECT, INSERT ON symptom_doctor_finder.auth_user TO 'sdf_admin_creator_role';

CREATE USER IF NOT EXISTS 'sdf_admin_creator'@'localhost' IDENTIFIED BY RANDOM PASSWORD;
GRANT 'sdf_admin_creator_role' TO 'sdf_admin_creator'@'localhost';
SET DEFAULT ROLE 'sdf_admin_creator_role' TO 'sdf_admin_creator'@'localhost';

-- Do not grant the maintenance account CREATE USER, GRANT OPTION, schema DDL,
-- or global privileges. The DBA running this script remains responsible for
-- account lifecycle and schema migrations.
