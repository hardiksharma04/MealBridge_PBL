from datetime import datetime
from decimal import Decimal, InvalidOperation
import getpass
import os
import secrets

from flask import Flask, flash, g, redirect, render_template, request, url_for
import mysql.connector
from mysql.connector import Error


app = Flask(__name__)
app.secret_key = secrets.token_hex(24)

DB_CONFIG = {
    "host": os.getenv("MEALBRIDGE_DB_HOST", "localhost"),
    "user": os.getenv("MEALBRIDGE_DB_USER", "root"),
    "database": os.getenv("MEALBRIDGE_DB_NAME", "mealbridge"),
    "password": os.getenv("MEALBRIDGE_DB_PASSWORD"),
}
if DB_CONFIG["password"] is None:
    DB_CONFIG["password"] = getpass.getpass(
        f"MySQL password for {DB_CONFIG['user']} (press Enter if none): "
    )


def get_db():
    if "db" not in g:
        g.db = mysql.connector.connect(**DB_CONFIG)
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def fetch_all(sql, params=()):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        cursor.close()


def fetch_one(sql, params=()):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchone()
    finally:
        cursor.close()


def execute(sql, params=()):
    connection = get_db()
    cursor = connection.cursor()
    try:
        cursor.execute(sql, params)
        connection.commit()
        return cursor.lastrowid
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


@app.errorhandler(Error)
def handle_database_error(error):
    return render_template("error.html", message=str(error)), 500


@app.route("/")
def home():
    stats = {
        "available": fetch_one(
            """SELECT COUNT(*) AS total FROM FoodListing
               WHERE status = 'AVAILABLE' AND expiry_time > NOW()"""
        )["total"],
        "donors": fetch_one("SELECT COUNT(*) AS total FROM Donor")["total"],
        "ngos": fetch_one("SELECT COUNT(*) AS total FROM NGO")["total"],
        "volunteers": fetch_one("SELECT COUNT(*) AS total FROM Volunteer")["total"],
        "claims": fetch_one("SELECT COUNT(*) AS total FROM Claim")["total"],
    }
    listings = fetch_all(
        """SELECT f.listing_id, f.food_name, f.quantity_kg, f.pickup_area,
                  f.expiry_time, d.donor_name
           FROM FoodListing AS f
           JOIN Donor AS d ON d.donor_id = f.donor_id
           WHERE f.status = 'AVAILABLE' AND f.expiry_time > NOW()
           ORDER BY f.expiry_time"""
    )
    ngos = fetch_all("SELECT ngo_id, ngo_name FROM NGO ORDER BY ngo_name")
    recent_claims = fetch_all(
        """SELECT c.claim_id, c.ngo_id, f.food_name, n.ngo_name,
                  c.claim_status, c.claim_time, p.pickup_id, p.pickup_status,
                  p.volunteer_id, v.volunteer_name
           FROM Claim AS c
           JOIN FoodListing AS f ON f.listing_id = c.listing_id
           JOIN NGO AS n ON n.ngo_id = c.ngo_id
           LEFT JOIN Pickup AS p ON p.claim_id = c.claim_id
           LEFT JOIN Volunteer AS v ON v.volunteer_id = p.volunteer_id
           ORDER BY c.claim_time DESC LIMIT 5"""
    )
    volunteers_by_ngo = {}
    for volunteer in fetch_all(
        "SELECT volunteer_id, ngo_id, volunteer_name FROM Volunteer ORDER BY volunteer_name"
    ):
        volunteers_by_ngo.setdefault(volunteer["ngo_id"], []).append(volunteer)
    return render_template(
        "index.html",
        stats=stats,
        listings=listings,
        ngos=ngos,
        claims=recent_claims,
        volunteers_by_ngo=volunteers_by_ngo,
    )


@app.route("/donors/new", methods=["GET", "POST"])
def new_donor():
    if request.method == "POST":
        name = request.form.get("donor_name", "").strip()
        donor_type = request.form.get("donor_type", "").strip()
        phone = request.form.get("phone", "").strip() or None
        area = request.form.get("area", "").strip()
        if not name or not donor_type or not area:
            flash("Please fill in the donor name, type, and area.", "error")
        else:
            donor_id = execute(
                """INSERT INTO Donor (donor_name, donor_type, phone, area)
                   VALUES (%s, %s, %s, %s)""",
                (name, donor_type, phone, area),
            )
            flash(f"Donor added (ID {donor_id}).", "success")
            return redirect(url_for("home"))
    return render_template("donor_form.html")


@app.route("/ngos/new", methods=["GET", "POST"])
def new_ngo():
    if request.method == "POST":
        name = request.form.get("ngo_name", "").strip()
        phone = request.form.get("phone", "").strip() or None
        area = request.form.get("area", "").strip()
        if not name or not area:
            flash("Please fill in the NGO name and area.", "error")
        else:
            ngo_id = execute(
                "INSERT INTO NGO (ngo_name, phone, area) VALUES (%s, %s, %s)",
                (name, phone, area),
            )
            flash(f"NGO added (ID {ngo_id}).", "success")
            return redirect(url_for("home"))
    return render_template("ngo_form.html")


@app.route("/volunteers/new", methods=["GET", "POST"])
def new_volunteer():
    ngos = fetch_all("SELECT ngo_id, ngo_name FROM NGO ORDER BY ngo_name")
    if request.method == "POST":
        ngo_id = request.form.get("ngo_id", type=int)
        name = request.form.get("volunteer_name", "").strip()
        phone = request.form.get("phone", "").strip() or None
        if not ngo_id or not name:
            flash("Choose an NGO and enter the volunteer's name.", "error")
        else:
            volunteer_id = execute(
                """INSERT INTO Volunteer (ngo_id, volunteer_name, phone)
                   VALUES (%s, %s, %s)""",
                (ngo_id, name, phone),
            )
            flash(f"Volunteer added (ID {volunteer_id}).", "success")
            return redirect(url_for("home"))
    return render_template("volunteer_form.html", ngos=ngos)


@app.route("/listings/new", methods=["GET", "POST"])
def new_listing():
    donors = fetch_all("SELECT donor_id, donor_name FROM Donor ORDER BY donor_name")
    if request.method == "POST":
        donor_id = request.form.get("donor_id", type=int)
        food_name = request.form.get("food_name", "").strip()
        pickup_area = request.form.get("pickup_area", "").strip()
        try:
            quantity = Decimal(request.form.get("quantity_kg", ""))
            expiry_time = datetime.strptime(
                request.form.get("expiry_time", ""), "%Y-%m-%dT%H:%M"
            )
            if quantity <= 0:
                raise InvalidOperation
            if expiry_time <= datetime.now():
                flash("Choose an expiry time in the future.", "error")
                return render_template("listing_form.html", donors=donors)
        except (ValueError, InvalidOperation):
            flash("Enter a positive quantity and a valid future expiry time.", "error")
            return render_template("listing_form.html", donors=donors)

        if not donor_id or not food_name or not pickup_area:
            flash("Please complete all required fields.", "error")
        else:
            listing_id = execute(
                """INSERT INTO FoodListing
                   (donor_id, food_name, quantity_kg, pickup_area, expiry_time)
                   VALUES (%s, %s, %s, %s, %s)""",
                (donor_id, food_name, quantity, pickup_area, expiry_time),
            )
            flash(f"Food listing added (ID {listing_id}).", "success")
            return redirect(url_for("home"))
    return render_template("listing_form.html", donors=donors)


@app.route("/claim/<int:listing_id>", methods=["POST"])
def claim_listing(listing_id):
    ngo_id = request.form.get("ngo_id", type=int)
    if not ngo_id:
        flash("Choose an NGO before claiming food.", "error")
        return redirect(url_for("home"))

    cursor = get_db().cursor()
    try:
        cursor.callproc("claim_listing", (listing_id, ngo_id))
        for result in cursor.stored_results():
            result.fetchall()
            result.close()
        flash("Food claimed successfully.", "success")
    except Error as error:
        flash(f"Claim could not be saved: {error}", "error")
    finally:
        cursor.close()
    return redirect(url_for("home"))


@app.route("/claims/<int:claim_id>/pickup", methods=["POST"])
def assign_pickup(claim_id):
    volunteer_id = request.form.get("volunteer_id", type=int)
    if not volunteer_id:
        flash("Choose a volunteer for this pickup.", "error")
        return redirect(url_for("home"))

    claim = fetch_one(
        """SELECT c.ngo_id, c.claim_status, p.pickup_id
           FROM Claim AS c LEFT JOIN Pickup AS p ON p.claim_id = c.claim_id
           WHERE c.claim_id = %s""",
        (claim_id,),
    )
    volunteer = fetch_one(
        "SELECT ngo_id FROM Volunteer WHERE volunteer_id = %s", (volunteer_id,)
    )
    if not claim or claim["claim_status"] != "CLAIMED" or claim["pickup_id"]:
        flash("This claim is not ready for a new pickup assignment.", "error")
    elif not volunteer or volunteer["ngo_id"] != claim["ngo_id"]:
        flash("Choose a volunteer who belongs to the NGO that claimed this food.", "error")
    else:
        execute(
            "INSERT INTO Pickup (claim_id, volunteer_id) VALUES (%s, %s)",
            (claim_id, volunteer_id),
        )
        flash("Volunteer assigned. Mark the pickup after the food is collected.", "success")
    return redirect(url_for("home"))


@app.route("/pickups/<int:pickup_id>/complete", methods=["POST"])
def complete_pickup(pickup_id):
    connection = get_db()
    cursor = connection.cursor()
    try:
        connection.start_transaction()
        cursor.execute(
            """UPDATE Pickup SET pickup_status = 'PICKED_UP', pickup_time = NOW()
               WHERE pickup_id = %s AND pickup_status = 'ASSIGNED'""",
            (pickup_id,),
        )
        if cursor.rowcount != 1:
            connection.rollback()
            flash("This pickup is not waiting to be completed.", "error")
            return redirect(url_for("home"))
        cursor.execute(
            """UPDATE Claim AS c JOIN Pickup AS p ON p.claim_id = c.claim_id
               SET c.claim_status = 'PICKED_UP'
               WHERE p.pickup_id = %s AND c.claim_status = 'CLAIMED'""",
            (pickup_id,),
        )
        if cursor.rowcount != 1:
            connection.rollback()
            flash("The claim status could not be updated; no pickup changes were saved.", "error")
            return redirect(url_for("home"))
        connection.commit()
        flash("Pickup recorded. The food has been marked PICKED_UP.", "success")
    except Error:
        connection.rollback()
        raise
    finally:
        cursor.close()
    return redirect(url_for("home"))


@app.route("/claims/<int:claim_id>/advance", methods=["POST"])
def advance_claim(claim_id):
    claim = fetch_one(
        "SELECT claim_status FROM Claim WHERE claim_id = %s", (claim_id,)
    )
    next_status = "DISTRIBUTED" if claim and claim["claim_status"] == "PICKED_UP" else None
    if next_status:
        execute(
            "UPDATE Claim SET claim_status = %s WHERE claim_id = %s",
            (next_status, claim_id),
        )
        flash(f"Claim status updated to {next_status}.", "success")
    else:
        flash("Claim not found or already distributed.", "error")
    return redirect(url_for("home"))


@app.route("/reports")
def reports():
    donor_rows = fetch_all(
        """SELECT d.donor_name, COALESCE(SUM(f.quantity_kg), 0) AS total_food_kg
           FROM Donor AS d
           LEFT JOIN FoodListing AS f ON f.donor_id = d.donor_id
           GROUP BY d.donor_id, d.donor_name
           ORDER BY d.donor_name"""
    )
    ngo_rows = fetch_all(
        """SELECT n.ngo_name, COUNT(c.claim_id) AS claims_made
           FROM NGO AS n
           LEFT JOIN Claim AS c ON c.ngo_id = n.ngo_id
           GROUP BY n.ngo_id, n.ngo_name
           ORDER BY n.ngo_name"""
    )
    volunteer_rows = fetch_all(
        """SELECT v.volunteer_name, n.ngo_name,
                  COUNT(p.pickup_id) AS assigned_pickups,
                  COALESCE(SUM(CASE WHEN p.pickup_status = 'PICKED_UP' THEN 1 ELSE 0 END), 0)
                      AS completed_pickups
           FROM Volunteer AS v
           JOIN NGO AS n ON n.ngo_id = v.ngo_id
           LEFT JOIN Pickup AS p ON p.volunteer_id = v.volunteer_id
           GROUP BY v.volunteer_id, v.volunteer_name, n.ngo_name
           ORDER BY v.volunteer_name"""
    )
    return render_template(
        "reports.html", donors=donor_rows, ngos=ngo_rows, volunteers=volunteer_rows
    )


if __name__ == "__main__":
    print("MealBridge website: http://127.0.0.1:5000")
    print("Keep this window open while using the site. Press Ctrl+C to stop.")
    app.run(host="127.0.0.1", port=5000, debug=False)
