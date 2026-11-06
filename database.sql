CREATE DATABASE IF NOT EXISTS mealbridge;
USE mealbridge;

CREATE TABLE IF NOT EXISTS Donor (
    donor_id INT AUTO_INCREMENT PRIMARY KEY,
    donor_name VARCHAR(100) NOT NULL,
    donor_type VARCHAR(30) NOT NULL,
    phone VARCHAR(20),
    area VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS NGO (
    ngo_id INT AUTO_INCREMENT PRIMARY KEY,
    ngo_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    area VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS FoodListing (
    listing_id INT AUTO_INCREMENT PRIMARY KEY,
    donor_id INT NOT NULL,
    food_name VARCHAR(100) NOT NULL,
    quantity_kg DECIMAL(7,2) NOT NULL CHECK (quantity_kg > 0),
    pickup_area VARCHAR(100) NOT NULL,
    expiry_time DATETIME NOT NULL,
    status ENUM('AVAILABLE', 'CLAIMED', 'EXPIRED') NOT NULL DEFAULT 'AVAILABLE',
    FOREIGN KEY (donor_id) REFERENCES Donor(donor_id)
);

CREATE TABLE IF NOT EXISTS Claim (
    claim_id INT AUTO_INCREMENT PRIMARY KEY,
    listing_id INT NOT NULL UNIQUE,
    ngo_id INT NOT NULL,
    claim_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    claim_status ENUM('CLAIMED', 'PICKED_UP', 'DISTRIBUTED') NOT NULL DEFAULT 'CLAIMED',
    FOREIGN KEY (listing_id) REFERENCES FoodListing(listing_id),
    FOREIGN KEY (ngo_id) REFERENCES NGO(ngo_id)
);

CREATE TABLE IF NOT EXISTS Volunteer (
    volunteer_id INT AUTO_INCREMENT PRIMARY KEY,
    ngo_id INT NOT NULL,
    volunteer_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    FOREIGN KEY (ngo_id) REFERENCES NGO(ngo_id)
);

CREATE TABLE IF NOT EXISTS Pickup (
    pickup_id INT AUTO_INCREMENT PRIMARY KEY,
    claim_id INT NOT NULL UNIQUE,
    volunteer_id INT NOT NULL,
    assigned_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    pickup_time DATETIME NULL,
    pickup_status ENUM('ASSIGNED', 'PICKED_UP') NOT NULL DEFAULT 'ASSIGNED',
    FOREIGN KEY (claim_id) REFERENCES Claim(claim_id),
    FOREIGN KEY (volunteer_id) REFERENCES Volunteer(volunteer_id)
);

-- Small sample dataset. The named records are inserted only once.
INSERT INTO Donor (donor_name, donor_type, phone, area)
SELECT 'Sunrise Cafe', 'Cafe', '9876501001', 'Sector 18'
WHERE NOT EXISTS (SELECT 1 FROM Donor WHERE donor_name = 'Sunrise Cafe');

INSERT INTO Donor (donor_name, donor_type, phone, area)
SELECT 'Green Leaf Canteen', 'Canteen', '9876501002', 'Sector 62'
WHERE NOT EXISTS (SELECT 1 FROM Donor WHERE donor_name = 'Green Leaf Canteen');

INSERT INTO NGO (ngo_name, phone, area)
SELECT 'Hope Community Kitchen', '9876502001', 'Sector 18'
WHERE NOT EXISTS (SELECT 1 FROM NGO WHERE ngo_name = 'Hope Community Kitchen');

INSERT INTO NGO (ngo_name, phone, area)
SELECT 'Care for All Foundation', '9876502002', 'Sector 62'
WHERE NOT EXISTS (SELECT 1 FROM NGO WHERE ngo_name = 'Care for All Foundation');

INSERT INTO FoodListing (donor_id, food_name, quantity_kg, pickup_area, expiry_time)
SELECT donor_id, 'Vegetable meals', 12.00, 'Sector 18', DATE_ADD(NOW(), INTERVAL 5 HOUR)
FROM Donor WHERE donor_name = 'Sunrise Cafe'
  AND NOT EXISTS (SELECT 1 FROM FoodListing WHERE food_name = 'Vegetable meals' AND pickup_area = 'Sector 18');

INSERT INTO FoodListing (donor_id, food_name, quantity_kg, pickup_area, expiry_time)
SELECT donor_id, 'Fresh bread', 8.00, 'Sector 62', DATE_ADD(NOW(), INTERVAL 4 HOUR)
FROM Donor WHERE donor_name = 'Green Leaf Canteen'
  AND NOT EXISTS (SELECT 1 FROM FoodListing WHERE food_name = 'Fresh bread' AND pickup_area = 'Sector 62');

-- Refresh the two available demo offers if their sample expiry time has passed.
-- Also reset an expired demo offer if no claim was ever made. Claimed offers are unchanged.
UPDATE FoodListing AS f
JOIN Donor AS d ON d.donor_id = f.donor_id
SET f.status = 'AVAILABLE',
    f.expiry_time = DATE_ADD(NOW(), INTERVAL 1 DAY)
WHERE f.status IN ('AVAILABLE', 'EXPIRED')
  AND f.listing_id > 0
  AND f.expiry_time <= NOW()
  AND NOT EXISTS (SELECT 1 FROM Claim AS c WHERE c.listing_id = f.listing_id)
  AND ((d.donor_name = 'Sunrise Cafe' AND f.food_name = 'Vegetable meals' AND f.pickup_area = 'Sector 18')
    OR (d.donor_name = 'Green Leaf Canteen' AND f.food_name = 'Fresh bread' AND f.pickup_area = 'Sector 62'));

-- Browse food that is still available and within its safe pickup time.
SELECT listing_id, food_name, quantity_kg, pickup_area, expiry_time
FROM FoodListing
WHERE status = 'AVAILABLE' AND expiry_time > NOW()
ORDER BY expiry_time;

-- Donation listing history with the donor name.
SELECT d.donor_name, f.food_name, f.quantity_kg, f.status, f.expiry_time
FROM FoodListing AS f
JOIN Donor AS d ON d.donor_id = f.donor_id
ORDER BY f.listing_id;

-- Move a claim through its simple lifecycle. Replace 1 with a real claim_id.
-- UPDATE Claim SET claim_status = 'PICKED_UP' WHERE claim_id = 1;
-- UPDATE Claim SET claim_status = 'DISTRIBUTED' WHERE claim_id = 1;

-- Summary: total food offered by each donor.
SELECT d.donor_name, COALESCE(SUM(f.quantity_kg), 0) AS total_food_kg
FROM Donor AS d
LEFT JOIN FoodListing AS f ON f.donor_id = d.donor_id
GROUP BY d.donor_id, d.donor_name;

-- Summary: claims made by each NGO.
SELECT n.ngo_name, COUNT(c.claim_id) AS claims_made
FROM NGO AS n
LEFT JOIN Claim AS c ON c.ngo_id = n.ngo_id
GROUP BY n.ngo_id, n.ngo_name;
