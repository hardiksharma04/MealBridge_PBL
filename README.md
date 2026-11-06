# MealBridge - DBMS Minor Project

MealBridge connects places with extra safe food (such as cafes and canteens) with NGOs that can collect it. This beginner version focuses on the database and the basic donation-to-claim process.

## Project plan

1. Create donor, NGO, food listing, claim, volunteer, and pickup tables.
2. Connect the tables with primary keys and foreign keys.
3. Add sample donors, NGOs, and food listings.
4. Browse food that is available before its expiry time.
5. Record an NGO's claim and assign a volunteer pickup.
6. Automatically expire unclaimed food and show summary reports for donors, NGOs, and volunteers.

## Scope for this first version

The project uses six tables and MySQL 8, with a simple local website in Python Flask. It demonstrates a real community problem without adding user login, maps, notifications, or administrator screens. These features can be future improvements. The claim lifecycle is CLAIMED, PICKED_UP, and DISTRIBUTED; volunteer assignment and pickup time are stored separately in the Pickup table. The older text menu remains in `app.py`; use `web_app.py` for the complete volunteer and pickup workflow.

## How to run

1. Install MySQL Community Server and open MySQL Workbench.
2. Run `database.sql`. It creates the `mealbridge` database and tables, adds sample data, and displays example queries and reports.
3. Run `claim_example.sql` to create the safe claim procedure and the two validation triggers. It also displays the listing and NGO IDs.
4. Run `auto_expiry.sql` to enable the MySQL Event Scheduler and create the event that expires unclaimed listings once a minute.
5. Install the Python dependencies in a terminal: `python -m pip install -r requirements.txt`.
6. Start the website with `python web_app.py`. Enter your MySQL password when asked.
7. Open `http://127.0.0.1:5000` in your browser. Keep the PowerShell window open while using the website; press Ctrl+C there to stop it.
8. Use the navigation to register donors, NGOs, and volunteers; post food; claim listings; assign pickups; update distribution progress; and view reports.

The website expects MySQL Server to be running, and it needs the procedure and triggers created in step 3. `validate_claim_before_insert` verifies a claim's listing is claimed and unexpired. `validate_pickup_before_insert` verifies the volunteer belongs to the NGO that made the claim. The event in step 4 changes AVAILABLE listings to EXPIRED after their expiry time passes. `SET PERSIST event_scheduler = ON` requires permission to change a MySQL server setting. The starter data includes two donors, two NGOs, and two food listings. Running `database.sql` again does not duplicate those sample records; it refreshes an expired demo listing only if it has not been claimed.

The default connection is `localhost`, user `root`, database `mealbridge`. The app asks for the password without displaying it. In PowerShell, if you use a different account or host, set connection settings for the current terminal before starting the app, for example:

```powershell
$env:MEALBRIDGE_DB_HOST = "localhost"
$env:MEALBRIDGE_DB_USER = "your_mysql_user"
python web_app.py
```

Do not save your database password in the project files.

## The six tables

- **Donor** stores cafes, restaurants, and canteens that offer surplus food.
- **NGO** stores organisations that can collect and distribute the food.
- **FoodListing** stores the food, amount, pickup area, expiry time, and current availability.
- **Claim** records which NGO reserved a listing and its simple progress status.
- **Volunteer** stores people who help an NGO with collection.
- **Pickup** connects one claim to its assigned volunteer and pickup status/time.

`listing_id` is unique in Claim, so one food listing cannot be recorded as claimed by two NGOs. `claim_id` is unique in Pickup, so each claim has at most one pickup assignment. Foreign keys connect listings, claims, NGOs, volunteers, and pickups.

## DBMS ideas you can explain

- A **table** stores one kind of information.
- A **primary key** identifies one row, for example `donor_id`.
- A **foreign key** links related rows, for example `FoodListing.donor_id` links to `Donor`.
- A **constraint** protects data. `quantity_kg > 0` rejects zero or negative amounts; `UNIQUE` prevents repeat claims.
- A **JOIN** combines related tables so a report can show a donor name beside its food listing.
- A **transaction** groups the claim update and claim record. Commit keeps both changes; rollback cancels them. The procedure uses a row lock while it checks a listing so two claims cannot proceed at once.
- A **trigger** runs automatically before a Claim or Pickup row is inserted. The triggers check that the listing is valid and that the pickup volunteer belongs to the claiming NGO.
- A **scheduled event** runs once a minute to change expired, unclaimed listings to EXPIRED. A trigger cannot run just because time passes, so the MySQL Event Scheduler handles this timed task.

## Simple class presentation

1. Explain the problem: edible extra food may be wasted while nearby NGOs need food.
2. Describe the six tables and relationships: Donor to FoodListing; FoodListing to Claim; NGO to Claim and Volunteer; Claim to Pickup; Volunteer to Pickup.
3. Show available food and explain how the scheduled event expires unclaimed listings.
4. Demonstrate a claim, explaining the transaction and validation trigger.
5. Register a volunteer and assign them to a claim; show pickup and distribution progress.
6. Show donor, NGO, and volunteer pickup reports.

## Limitations and future improvements

This is a local student prototype. It has no user login or administrator verification, beneficiary distribution records, maps, or response-time reports.
