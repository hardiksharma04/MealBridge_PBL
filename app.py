from datetime import datetime
from decimal import Decimal, InvalidOperation
import getpass
import os
import sys

import mysql.connector
from mysql.connector import Error


def connect_database():
    """Connect using environment settings, prompting for a password if needed."""
    config = {
        "host": os.getenv("MEALBRIDGE_DB_HOST", "localhost"),
        "user": os.getenv("MEALBRIDGE_DB_USER", "root"),
        "database": os.getenv("MEALBRIDGE_DB_NAME", "mealbridge"),
        "password": os.getenv("MEALBRIDGE_DB_PASSWORD"),
    }
    if config["password"] is None:
        config["password"] = getpass.getpass(
            f"MySQL password for {config['user']} (press Enter if none): "
        )
    return mysql.connector.connect(**config)


def print_rows(headers, rows):
    """Print a small result set as a readable text table."""
    if not rows:
        print("\nNo records found.\n")
        return
    values = [["" if value is None else str(value) for value in row] for row in rows]
    widths = [len(str(header)) for header in headers]
    for row in values:
        for index, value in enumerate(row):
            widths[index] = min(max(widths[index], len(value)), 28)

    def line(row):
        cells = []
        for index, value in enumerate(row):
            if len(value) <= widths[index]:
                shown = value
            elif widths[index] <= 3:
                shown = value[: widths[index]]
            else:
                shown = value[: widths[index] - 3] + "..."
            cells.append(shown.ljust(widths[index]))
        return " | ".join(cells)

    print()
    print(line(headers))
    print("-+-".join("-" * width for width in widths))
    for row in values:
        print(line(row))
    print()


def query_rows(connection, query, parameters=()):
    cursor = connection.cursor()
    try:
        cursor.execute(query, parameters)
        return cursor.fetchall()
    finally:
        cursor.close()


def browse_listings(connection):
    rows = query_rows(
        connection,
        """SELECT listing_id, food_name, quantity_kg, pickup_area, expiry_time
           FROM FoodListing
           WHERE status = 'AVAILABLE' AND expiry_time > NOW()
           ORDER BY expiry_time""",
    )
    print_rows(["ID", "Food", "Kg", "Pickup area", "Expires"], rows)


def show_donors(connection):
    rows = query_rows(
        connection,
        "SELECT donor_id, donor_name, donor_type, area FROM Donor ORDER BY donor_name",
    )
    print_rows(["ID", "Donor", "Type", "Area"], rows)


def register_donor(connection):
    donor_name = input("Donor/business name: ").strip()
    donor_type = input("Type (cafe, restaurant, canteen, etc.): ").strip()
    phone = input("Phone (optional): ").strip() or None
    area = input("Area: ").strip()
    if not donor_name or not donor_type or not area:
        print("Name, type, and area are required.")
        return

    cursor = connection.cursor()
    try:
        cursor.execute(
            """INSERT INTO Donor (donor_name, donor_type, phone, area)
               VALUES (%s, %s, %s, %s)""",
            (donor_name, donor_type, phone, area),
        )
        connection.commit()
        print(f"Donor registered with ID {cursor.lastrowid}.")
    except Error as error:
        connection.rollback()
        print(f"Could not register donor: {error}")
    finally:
        cursor.close()


def register_ngo(connection):
    ngo_name = input("NGO name: ").strip()
    phone = input("Phone (optional): ").strip() or None
    area = input("Area: ").strip()
    if not ngo_name or not area:
        print("NGO name and area are required.")
        return

    cursor = connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO NGO (ngo_name, phone, area) VALUES (%s, %s, %s)",
            (ngo_name, phone, area),
        )
        connection.commit()
        print(f"NGO registered with ID {cursor.lastrowid}.")
    except Error as error:
        connection.rollback()
        print(f"Could not register NGO: {error}")
    finally:
        cursor.close()


def add_listing(connection):
    show_donors(connection)
    try:
        donor_id = int(input("Donor ID: ").strip())
        food_name = input("Food name: ").strip()
        if not food_name:
            print("Food name cannot be blank.")
            return
        quantity = Decimal(input("Quantity in kg: ").strip())
        if quantity <= 0:
            print("Quantity must be greater than zero.")
            return
        pickup_area = input("Pickup area: ").strip()
        expiry_text = input("Expiry (YYYY-MM-DD HH:MM): ").strip()
        expiry_time = datetime.strptime(expiry_text, "%Y-%m-%d %H:%M")
        if not pickup_area:
            print("Pickup area cannot be blank.")
            return
        if expiry_time <= datetime.now():
            print("Expiry time must be in the future.")
            return
    except (ValueError, InvalidOperation):
        print("Please enter a valid ID, quantity, and date/time.")
        return

    cursor = connection.cursor()
    try:
        cursor.execute(
            """INSERT INTO FoodListing
               (donor_id, food_name, quantity_kg, pickup_area, expiry_time)
               VALUES (%s, %s, %s, %s, %s)""",
            (donor_id, food_name, quantity, pickup_area, expiry_time),
        )
        connection.commit()
        print(f"Food listing added with ID {cursor.lastrowid}.")
    except Error as error:
        connection.rollback()
        print(f"Could not add listing: {error}")
    finally:
        cursor.close()


def make_claim(connection):
    browse_listings(connection)
    ngos = query_rows(connection, "SELECT ngo_id, ngo_name, area FROM NGO ORDER BY ngo_name")
    print_rows(["ID", "NGO", "Area"], ngos)
    try:
        listing_id = int(input("Listing ID to claim: ").strip())
        ngo_id = int(input("NGO ID making the claim: ").strip())
    except ValueError:
        print("Please enter whole-number IDs.")
        return

    cursor = connection.cursor()
    try:
        cursor.callproc("claim_listing", (listing_id, ngo_id))
        # Drain the procedure's confirmation result so the connection is ready
        # for the next menu action.
        for result in cursor.stored_results():
            result.fetchall()
            result.close()
        print("Claim saved. The listing is now marked CLAIMED.")
    except Error as error:
        print(f"Claim was not saved: {error}")
    finally:
        cursor.close()


def listing_history(connection):
    rows = query_rows(
        connection,
        """SELECT f.listing_id, f.food_name, d.donor_name, f.quantity_kg,
                  CASE WHEN f.status = 'AVAILABLE' AND f.expiry_time <= NOW()
                       THEN 'EXPIRED' ELSE f.status END AS display_status,
                  f.expiry_time
           FROM FoodListing AS f
           JOIN Donor AS d ON d.donor_id = f.donor_id
           ORDER BY f.listing_id""",
    )
    print_rows(["ID", "Food", "Donor", "Kg", "Status", "Expires"], rows)


def donor_report(connection):
    rows = query_rows(
        connection,
        """SELECT d.donor_name, COALESCE(SUM(f.quantity_kg), 0) AS total_food_kg
           FROM Donor AS d
           LEFT JOIN FoodListing AS f ON f.donor_id = d.donor_id
           GROUP BY d.donor_id, d.donor_name
           ORDER BY d.donor_name""",
    )
    print_rows(["Donor", "Food offered (kg)"], rows)


def ngo_report(connection):
    rows = query_rows(
        connection,
        """SELECT n.ngo_name, COUNT(c.claim_id) AS claims_made
           FROM NGO AS n
           LEFT JOIN Claim AS c ON c.ngo_id = n.ngo_id
           GROUP BY n.ngo_id, n.ngo_name
           ORDER BY n.ngo_name""",
    )
    print_rows(["NGO", "Claims"], rows)


def update_claim_status(connection):
    rows = query_rows(
        connection,
        """SELECT c.claim_id, f.food_name, n.ngo_name, c.claim_status
           FROM Claim AS c
           JOIN FoodListing AS f ON f.listing_id = c.listing_id
           JOIN NGO AS n ON n.ngo_id = c.ngo_id
           ORDER BY c.claim_id""",
    )
    print_rows(["Claim ID", "Food", "NGO", "Current status"], rows)
    try:
        claim_id = int(input("Claim ID to update: ").strip())
    except ValueError:
        print("Please enter a whole-number ID.")
        return

    current = query_rows(
        connection,
        "SELECT claim_status FROM Claim WHERE claim_id = %s",
        (claim_id,),
    )
    if not current:
        print("Claim ID was not found.")
        return
    allowed_next = {"CLAIMED": "PICKED_UP", "PICKED_UP": "DISTRIBUTED"}
    next_status = allowed_next.get(current[0][0])
    if next_status is None:
        print("This claim is already DISTRIBUTED.")
        return
    answer = input(f"Change status to {next_status}? (y/n): ").strip().lower()
    if answer != "y":
        print("No change made.")
        return

    cursor = connection.cursor()
    try:
        cursor.execute(
            "UPDATE Claim SET claim_status = %s WHERE claim_id = %s",
            (next_status, claim_id),
        )
        connection.commit()
        print(f"Claim status updated to {next_status}.")
    except Error as error:
        connection.rollback()
        print(f"Could not update claim: {error}")
    finally:
        cursor.close()


def main():
    try:
        connection = connect_database()
    except Error as error:
        print("Could not connect to MySQL.")
        print("Check that MySQL Server is running and database.sql has been run.")
        print(f"MySQL says: {error}")
        return 1

    actions = {
        "1": browse_listings,
        "2": add_listing,
        "3": make_claim,
        "4": listing_history,
        "5": donor_report,
        "6": ngo_report,
        "7": update_claim_status,
    }
    try:
        while True:
            print("\n=== MealBridge ===")
            print("1. Browse available food")
            print("2. Add a food listing")
            print("3. Claim a food listing")
            print("4. View listing history")
            print("5. Donor food report")
            print("6. NGO claim report")
            print("7. Update pickup/distribution status")
            print("8. Register a donor")
            print("9. Register an NGO")
            print("0. Exit")
            choice = input("Choose an option: ").strip()
            if choice == "0":
                break
            action = actions.get(choice)
            if choice == "8":
                action = register_donor
            elif choice == "9":
                action = register_ngo
            if action is None:
                print("Choose one of the menu numbers shown.")
                continue
            try:
                action(connection)
            except Error as error:
                print(f"Database operation failed: {error}")
    except (KeyboardInterrupt, EOFError):
        print("\nClosing MealBridge.")
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
