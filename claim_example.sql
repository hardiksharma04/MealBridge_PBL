USE mealbridge;

DROP TRIGGER IF EXISTS validate_claim_before_insert;
DROP TRIGGER IF EXISTS validate_pickup_before_insert;
DROP PROCEDURE IF EXISTS claim_listing;
DELIMITER $$

CREATE PROCEDURE claim_listing(IN p_listing_id INT, IN p_ngo_id INT)
BEGIN
    DECLARE v_status VARCHAR(15);
    DECLARE v_expiry_time DATETIME;

    -- If any SQL command fails, undo the whole claim and return the error.
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    DECLARE EXIT HANDLER FOR NOT FOUND
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    -- Lock the selected listing so another claim cannot change it at the same time.
    SELECT status, expiry_time
    INTO v_status, v_expiry_time
    FROM FoodListing
    WHERE listing_id = p_listing_id
    FOR UPDATE;

    IF v_status <> 'AVAILABLE' OR v_expiry_time <= NOW() THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'This food listing is not available or has expired';
    END IF;

    UPDATE FoodListing
    SET status = 'CLAIMED'
    WHERE listing_id = p_listing_id;

    INSERT INTO Claim (listing_id, ngo_id)
    VALUES (p_listing_id, p_ngo_id);

    COMMIT;

    SELECT 'Claim saved successfully' AS result;
END$$

-- Database trigger: allow a claim record only after its listing has been
-- marked CLAIMED and while the safe pickup time is still in the future.
CREATE TRIGGER validate_claim_before_insert
BEFORE INSERT ON Claim
FOR EACH ROW
BEGIN
    DECLARE v_status VARCHAR(15);
    DECLARE v_expiry_time DATETIME;

    SELECT status, expiry_time
    INTO v_status, v_expiry_time
    FROM FoodListing
    WHERE listing_id = NEW.listing_id;

    IF v_status <> 'CLAIMED' OR v_expiry_time <= NOW() THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Claim requires a claimed, unexpired food listing';
    END IF;
END$$

-- Ensure the pickup volunteer belongs to the NGO that claimed the food.
CREATE TRIGGER validate_pickup_before_insert
BEFORE INSERT ON Pickup
FOR EACH ROW
BEGIN
    DECLARE v_claim_ngo_id INT;
    DECLARE v_claim_status VARCHAR(15);
    DECLARE v_volunteer_ngo_id INT;

    SELECT ngo_id, claim_status
    INTO v_claim_ngo_id, v_claim_status
    FROM Claim
    WHERE claim_id = NEW.claim_id;

    SELECT ngo_id
    INTO v_volunteer_ngo_id
    FROM Volunteer
    WHERE volunteer_id = NEW.volunteer_id;

    IF v_claim_status <> 'CLAIMED' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'A pickup can only be assigned to a new claim';
    END IF;

    IF v_claim_ngo_id <> v_volunteer_ngo_id THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'The volunteer must belong to the claiming NGO';
    END IF;
END$$

DELIMITER ;

-- Check the sample IDs first. Use an AVAILABLE listing and an existing NGO.
SELECT listing_id, food_name, status, expiry_time FROM FoodListing;
SELECT ngo_id, ngo_name FROM NGO;

-- Replace 1, 1 with the IDs you want to use.
-- CALL claim_listing(1, 1);

-- The procedure rejects unavailable or expired listings. A UNIQUE constraint
-- on Claim.listing_id also prevents the same listing from being claimed twice.
