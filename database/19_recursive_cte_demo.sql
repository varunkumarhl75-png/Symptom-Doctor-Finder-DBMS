USE symptom_doctor_finder;

-- Non-destructive recursive CTE: report future appointment-slot counts by
-- calendar date for the next seven days. The source slot rows may include
-- demonstration schedules; this query does not certify real provider hours.
WITH RECURSIVE calendar_dates (slot_date) AS (
    -- Anchor member: begin with the current database date.
    SELECT CURRENT_DATE

    UNION ALL

    -- Recursive member: add one day to the date produced by the prior row.
    -- Termination condition: stop once the seventh date has been generated.
    SELECT slot_date + INTERVAL 1 DAY
    FROM calendar_dates
    WHERE slot_date < CURRENT_DATE + INTERVAL 6 DAY
),
available_slot_counts AS (
    SELECT
        sl.slot_date,
        COUNT(*) AS available_slots
    FROM appointment_slot sl
    WHERE TIMESTAMP(sl.slot_date, sl.start_time) >= CURRENT_TIMESTAMP
      AND NOT EXISTS (
          SELECT 1
          FROM appointment a
          WHERE a.slot_id = sl.slot_id
            AND a.status <> 'CANCELLED'
      )
    GROUP BY sl.slot_date
)
SELECT
    calendar_dates.slot_date,
    COALESCE(available_slot_counts.available_slots, 0) AS available_slots
FROM calendar_dates
LEFT JOIN available_slot_counts
    ON available_slot_counts.slot_date = calendar_dates.slot_date
ORDER BY calendar_dates.slot_date;
