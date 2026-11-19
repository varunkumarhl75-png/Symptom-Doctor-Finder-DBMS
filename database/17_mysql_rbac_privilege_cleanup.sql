USE symptom_doctor_finder;

-- One-time cleanup only for installations that already ran the older
-- database/16_mysql_rbac.sql, which granted these broader privileges.
-- Confirm those grants with SHOW GRANTS before running: REVOKE of a privilege
-- that is not present can fail. The corrected database/16 script does not add
-- any of the privileges removed here.
REVOKE INSERT ON symptom_doctor_finder.patient FROM 'sdf_app_role';
REVOKE INSERT ON symptom_doctor_finder.auth_user FROM 'sdf_app_role';
REVOKE SELECT ON symptom_doctor_finder.* FROM 'sdf_catalog_maintenance_role';
