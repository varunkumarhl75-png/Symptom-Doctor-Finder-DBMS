-- DML demonstration using only a session-scoped temporary table.
-- These statements never insert, update, or delete application records.
-- Run all statements in one MySQL session; the temporary table is dropped
-- automatically when that session closes.

CREATE TEMPORARY TABLE dml_demo_sample (
    sample_id INT PRIMARY KEY,
    sample_name VARCHAR(80) NOT NULL,
    status VARCHAR(20) NOT NULL,
    quantity INT NOT NULL
);

-- INSERT: create clearly labelled, temporary demonstration rows.
INSERT INTO dml_demo_sample (sample_id, sample_name, status, quantity)
VALUES
    (1, 'DML demo sample A', 'NEW', 2),
    (2, 'DML demo sample B', 'NEW', 5);

-- SELECT: inspect only the temporary sample rows.
SELECT sample_id, sample_name, status, quantity
FROM dml_demo_sample
ORDER BY sample_id;

-- UPDATE: change one temporary sample row using its primary key.
UPDATE dml_demo_sample
SET status = 'REVIEWED',
    quantity = 3
WHERE sample_id = 1;

-- SELECT: verify the update.
SELECT sample_id, sample_name, status, quantity
FROM dml_demo_sample
WHERE sample_id = 1;

-- DELETE: remove one temporary sample row using its primary key.
DELETE FROM dml_demo_sample
WHERE sample_id = 2;

-- SELECT: verify the deletion.
SELECT sample_id, sample_name, status, quantity
FROM dml_demo_sample
ORDER BY sample_id;

DROP TEMPORARY TABLE dml_demo_sample;
