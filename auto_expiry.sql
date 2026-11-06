-- Run in MySQL Workbench after database.sql.
-- This enables the MySQL Event Scheduler persistently and expires food every minute.
USE mealbridge;

SET PERSIST event_scheduler = ON;

DROP EVENT IF EXISTS expire_unclaimed_listings;
DELIMITER $$

CREATE EVENT expire_unclaimed_listings
ON SCHEDULE EVERY 1 MINUTE
ON COMPLETION PRESERVE
ENABLE
DO
BEGIN
    UPDATE FoodListing
    SET status = 'EXPIRED'
    WHERE status = 'AVAILABLE'
      AND expiry_time <= NOW()
      AND listing_id > 0;
END$$

DELIMITER ;

-- Check that the scheduler is enabled with:
-- SHOW VARIABLES LIKE 'event_scheduler';
-- Check the event with:
-- SHOW EVENTS FROM mealbridge;
