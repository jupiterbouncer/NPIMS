from datetime import date, datetime

import os
import mysql.connector
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
CORS(app)  # allows HTML frontend to call Flask


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "citizen.html")


@app.route("/<path:filename>")
def serve_file(filename):
    return send_from_directory(BASE_DIR, filename)


DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "demiladesubair",
    "database": "npims",
}


def get_db():
    return mysql.connector.connect(**DB_CONFIG)


# ── TEST ───
@app.route("/test")
def test_connection():
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT 1")
        db.close()
        return jsonify(
            {"status": "connected", "message": "Database connection successful"}
        )
    except Exception as e:
        return jsonify({"status": "failed", "message": str(e)}), 500


# ─────── CITIZEN ───────
@app.route("/api/citizen/check/<national_id>")
def check_citizen(national_id):
    db = get_db()
    cursor = db.cursor()
    # SELECT query that will run to the database
    cursor.execute(
        "SELECT NationalIDNo FROM CITIZEN WHERE NationalIDNo = %s", (national_id,)
    )
    exists = cursor.fetchone() is not None
    db.close()
    return jsonify({"exists": exists})


@app.route("/api/citizen/register", methods=["POST"])
def register_citizen():
    data = request.get_json()
    # Application layer date check
    if data["dob"] > str(date.today()):
        return jsonify({"message": "Date of birth cannot be in the future"}), 400

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO CITIZEN 
            (NationalIDNo, FirstName, LastName, OtherName, DOB, Gender, CountryCode, Email, Address)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
            (
                data["nationalIdNo"],
                data["firstName"],
                data["lastName"],
                data.get("otherName"),
                data["dob"],
                data["gender"],
                data["countryCode"],
                data["email"],
                data["address"],
            ),
        )
        db.commit()
        db.close()
        return jsonify({"message": "Citizen registered successfully"}), 201
    except mysql.connector.IntegrityError as e:
        return jsonify({"message": "National ID already exists"}), 409
    except Exception as e:
        return jsonify({"message": str(e)}), 500


# ─────── PASSPORT ───────────
@app.route("/api/passport/verify")
def verify_passport():
    national_id = request.args.get("nationalId")
    passport_no = request.args.get("passportNo")
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT p.PassportNo, p.ExpiryDate, p.PassportStatus,
                   c.FirstName, c.LastName
            FROM PASSPORT p
            JOIN CITIZEN c ON p.NationalIDNo = c.NationalIDNo
            WHERE p.NationalIDNo = %s AND p.PassportNo = %s
        """,
            (national_id, passport_no),
        )
        row = cursor.fetchone()
        db.close()
        if not row:
            return jsonify(
                {"valid": False, "message": "Passport not found for this citizen"}
            )
        if row["PassportStatus"] != "active":
            return jsonify(
                {"valid": False, "message": f"Passport is {row['PassportStatus']}"}
            )
        return jsonify(
            {
                "valid": True,
                "citizenName": f"{row['FirstName']} {row['LastName']}",
                "expiryDate": str(row["ExpiryDate"]),
            }
        )
    except Exception as e:
        return jsonify({"valid": False, "message": str(e)}), 500


# ──────────── TRAVEL ────────────
@app.route("/api/travel/citizen/<national_id>")
def get_citizen_travel(national_id):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT t.TravelID, t.PassportNo, t.EntryOrExit, t.ModeOfTravel,
                   t.DepartureCountry, t.ArrivalCountry, t.TravelDate,
                   b.BorderPostName AS borderPost
            FROM TRAVEL_RECORD t
            JOIN BORDER_POST b ON t.BorderPostID = b.BorderPostID
            WHERE t.NationalIDNo = %s
            ORDER BY t.TravelDate DESC
        """,
            (national_id,),
        )
        rows = cursor.fetchall()
        db.close()
        for r in rows:
            r["TravelDate"] = str(r["TravelDate"])
        return jsonify(rows)
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/travel/stats")
def travel_stats():
    try:
        db = get_db()
        cursor = db.cursor()
        today = datetime.today().date()
        first_of_month = today.replace(day=1)

        cursor.execute("SELECT COUNT(*) FROM TRAVEL_RECORD")
        total = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM TRAVEL_RECORD WHERE EntryOrExit = 'entry' AND TravelDate = %s",
            (today,),
        )
        entries = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM TRAVEL_RECORD WHERE EntryOrExit = 'exit' AND TravelDate = %s",
            (today,),
        )
        exits = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM TRAVEL_RECORD WHERE TravelDate >= %s",
            (first_of_month,),
        )
        month = cursor.fetchone()[0]

        db.close()
        return jsonify(
            {"total": total, "entries": entries, "exits": exits, "month": month}
        )
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/travel/all")
def get_all_travel():
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        query = """
            SELECT t.TravelID, t.NationalIDNo, t.PassportNo, t.EntryOrExit,
                   t.DepartureCountry, t.ArrivalCountry, t.ModeOfTravel,
                   t.TravelDate, b.BorderPostName AS borderPost
            FROM TRAVEL_RECORD t
            JOIN BORDER_POST b ON t.BorderPostID = b.BorderPostID
            WHERE 1=1
        """
        params = []

        q = request.args.get("q")
        if q:
            query += " AND (t.NationalIDNo LIKE %s OR t.PassportNo LIKE %s)"
            params += [f"%{q}%", f"%{q}%"]

        entry_exit = request.args.get("entryOrExit")
        if entry_exit:
            query += " AND t.EntryOrExit = %s"
            params.append(entry_exit)

        mode = request.args.get("mode")
        if mode:
            query += " AND t.ModeOfTravel = %s"
            params.append(mode)

        date_from = request.args.get("from")
        if date_from:
            query += " AND t.TravelDate >= %s"
            params.append(date_from)

        date_to = request.args.get("to")
        if date_to:
            query += " AND t.TravelDate <= %s"
            params.append(date_to)

        query += " ORDER BY t.TravelDate DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        db.close()
        for r in rows:
            r["TravelDate"] = str(r["TravelDate"])
        return jsonify(rows)
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/travel/log", methods=["POST"])
def log_travel():
    data = request.get_json()
    # Application layer date check
    if data["travelDate"] > str(date.today()):
        return jsonify({"message": "Travel date cannot be in the future"}), 400
    try:
        db = get_db()
        cursor = db.cursor()

        # Generate TravelID
        cursor.execute("SELECT COUNT(*) FROM TRAVEL_RECORD")
        count = cursor.fetchone()[0]
        travel_id = f"TRV-{count + 1:05d}"

        cursor.execute(
            """
            INSERT INTO TRAVEL_RECORD
            (TravelID, NationalIDNo, PassportNo, OfficerID, BorderPostID,
             DepartureCountry, ArrivalCountry, TravelDate, EntryOrExit, ModeOfTravel)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
            (
                travel_id,
                data["nationalIdNo"],
                data["passportNo"],
                data["officerId"],
                data["borderPostId"],
                data["departureCountry"],
                data["arrivalCountry"],
                data["travelDate"],
                data["entryOrExit"],
                data["modeOfTravel"],
            ),
        )
        db.commit()
        db.close()
        return jsonify({"message": "Travel record logged", "travelId": travel_id}), 201
    except Exception as e:
        return jsonify({"message": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)


"""
# Officers
GET  /api/officers/stats
GET  /api/officers?q=&post=
POST /api/officers/register
POST /api/officers/reassign

# Border
GET  /api/border/stats
GET  /api/border/posts?type=&country=
GET  /api/border/deployments
POST /api/border/register

# Visa
POST /api/visa/apply
GET  /api/visa/citizen/<national_id>
GET  /api/visa/pending
GET  /api/visa/all?q=&status=&type=
POST /api/visa/process

GET  /api/travel/citizen/<national_id>                  → citizen's own records
GET  /api/travel/stats                                  → counts for stat cards
GET  /api/travel/all?q=&entryOrExit=&mode=&from=&to=    → filtered records
POST /api/travel/log                                    → insert new travel record
GET  /api/passport/verify?nationalId=&passportNo=       → shared with passport page

GET  /api/citizen/check/<national_id>                   → { "exists": true/false }
POST /api/citizen/register                              → receives JSON, inserts into DB

/api/passport/apply and /api/payment/ 
    if data["applicationDate"] > str(date.today()):
        return jsonify({"message": "Application date cannot be in the future"}), 400

    if data["paymentDate"] > str(date.today()):
        return jsonify({"message": "Payment date cannot be in the future"}), 400

from datetime import date

if data["appointmentDate"] < str(date.today()) and data["appointmentStatus"] == "Scheduled":
    return jsonify({"message": "Scheduled appointments cannot be in the past"}), 400
"""
