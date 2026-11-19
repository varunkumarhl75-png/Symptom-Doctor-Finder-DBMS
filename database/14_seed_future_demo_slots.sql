USE symptom_doctor_finder;

-- Demo data only. This repeats the exact doctor/time combinations from the
-- seeded Monday-Friday schedule for matching weekdays over the next 30 days.
-- Confirm real provider availability before using this for anything beyond a
-- local demonstration.
INSERT INTO appointment_slot (
    doctor_id,
    slot_date,
    start_time,
    end_time
)
WITH RECURSIVE future_dates (slot_date) AS (
    SELECT CURRENT_DATE + INTERVAL 1 DAY
    UNION ALL
    SELECT slot_date + INTERVAL 1 DAY
    FROM future_dates
    WHERE slot_date < CURRENT_DATE + INTERVAL 30 DAY
),
seed_schedule AS (
    SELECT
        doctor_id,
        WEEKDAY(slot_date) AS weekday_number,
        start_time,
        end_time
    FROM appointment_slot
    WHERE slot_date BETWEEN '2026-10-05' AND '2026-10-09'
)
SELECT
    seed_schedule.doctor_id,
    future_dates.slot_date,
    seed_schedule.start_time,
    seed_schedule.end_time
FROM future_dates
JOIN seed_schedule
    ON WEEKDAY(future_dates.slot_date) = seed_schedule.weekday_number
WHERE NOT EXISTS (
    SELECT 1
    FROM appointment_slot existing_slot
    WHERE existing_slot.doctor_id = seed_schedule.doctor_id
      AND existing_slot.slot_date = future_dates.slot_date
      AND existing_slot.start_time = seed_schedule.start_time
      AND existing_slot.end_time = seed_schedule.end_time
);
USE symptom_doctor_finder;

SELECT
    slot_date,
    doctor_id,
    COUNT(*) AS available_slots
FROM appointment_slot
WHERE slot_date > CURRENT_DATE
  AND slot_date <= CURRENT_DATE + INTERVAL 30 DAY
GROUP BY slot_date, doctor_id
ORDER BY slot_date, doctor_id;
-- Verify future slots and confirm existing active appointments are untouched:
-- SELECT doctor_id, slot_date, start_time, end_time
-- FROM appointment_slot
-- WHERE slot_date > CURRENT_DATE
--   AND slot_date <= CURRENT_DATE + INTERVAL 30 DAY
-- ORDER BY slot_date, doctor_id, start_time;
--
-- After successfully executing this script, invalidate the app cache from the
-- project root in PowerShell:
-- .\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, r'.\app'); from cache import invalidate_caches; ok = invalidate_caches(); print('Cache invalidated' if ok else 'Cache invalidation failed'); raise SystemExit(0 if ok else 1)"
