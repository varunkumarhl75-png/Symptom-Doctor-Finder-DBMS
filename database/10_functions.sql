USE symptom_doctor_finder;

-- =========================================
-- FUNCTION 1
-- Calculate doctor's experience category
-- =========================================

DROP FUNCTION IF EXISTS get_experience_category;

DELIMITER $$

CREATE FUNCTION get_experience_category(
    p_experience INT
)
RETURNS VARCHAR(30)
DETERMINISTIC
BEGIN
    DECLARE category VARCHAR(30);

    IF p_experience >= 15 THEN
        SET category = 'Highly Experienced';
    ELSEIF p_experience >= 10 THEN
        SET category = 'Experienced';
    ELSEIF p_experience >= 5 THEN
        SET category = 'Moderately Experienced';
    ELSE
        SET category = 'Less Experienced';
    END IF;

    RETURN category;
END $$

DELIMITER ;


-- =========================================
-- FUNCTION 2
-- Calculate patient's age
-- =========================================

DROP FUNCTION IF EXISTS calculate_age;

DELIMITER $$

CREATE FUNCTION calculate_age(
    p_date_of_birth DATE
)
RETURNS INT
NOT DETERMINISTIC
BEGIN
    RETURN TIMESTAMPDIFF(
        YEAR,
        p_date_of_birth,
        CURDATE()
    );
END $$

DELIMITER ;


-- =========================================
-- FUNCTION 3
-- Get semantic match category
-- =========================================

DROP FUNCTION IF EXISTS get_similarity_category;

DELIMITER $$

CREATE FUNCTION get_similarity_category(
    p_score DECIMAL(5,4)
)
RETURNS VARCHAR(30)
DETERMINISTIC
BEGIN
    DECLARE category VARCHAR(30);

    IF p_score >= 0.90 THEN
        SET category = 'Strong Match';
    ELSEIF p_score >= 0.70 THEN
        SET category = 'Moderate Match';
    ELSE
        SET category = 'Weak Match';
    END IF;

    RETURN category;
END $$

DELIMITER ;