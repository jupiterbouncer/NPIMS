import os
import re
from datetime import date, datetime, timedelta

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

load_dotenv()

def to_camel(name):
    s = re.sub(r'([A-Z])', r'_\1', name).lower().lstrip('_')
    parts = s.split('_')
    return parts[0] + ''.join(p.capitalize() for p in parts[1:])

def camel_rows(rows):
    return [{to_camel(k): v for k, v in row.items()} for row in rows]

BASE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "pages"
)
app = Flask(__name__)
CORS(app)

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", 3306)),
    "user":     os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "npims"),
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)


def log_audit(cursor, officer_id, action_type, table_affected, record_id):
    try:
        cursor.execute(
            "INSERT INTO AUDIT_LOG (OfficerID, ActionType, TableAffected, RecordID) VALUES (%s, %s, %s, %s)",
            (officer_id, action_type, table_affected, str(record_id)),
        )
    except Exception:
        pass  # audit failure must never break the main operation

@app.route("/api/countries")
def get_countries():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT CountryCode, CountryName
        FROM COUNTRY
        WHERE IsActive = 1
        ORDER BY CountryName
    """)

    rows = cursor.fetchall()
    db.close()
    return jsonify(camel_rows(rows))


# ── STATIC FILES ───────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "citizen.html")


@app.route("/<path:filename>")
def serve_file(filename):
    return send_from_directory(BASE_DIR, filename)


# ── TEST ────────────────────────────────────────────────────────
@app.route("/test")
def test_connection():
    try:
        db = get_db()
        db.cursor().execute("SELECT 1")
        db.close()
        return jsonify(
            {"status": "connected", "message": "Database connection successful"}
        )
    except Exception as e:
        return jsonify({"status": "failed", "message": str(e)}), 500


# ══════════════════════════════════════════════════════════════
# CITIZEN
# ══════════════════════════════════════════════════════════════
@app.route("/api/citizen/check/<national_id>")
def check_citizen(national_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT NationalIDNo FROM CITIZEN WHERE NationalIDNo = %s", (national_id,)
    )
    exists = cursor.fetchone() is not None
    db.close()
    return jsonify({"exists": exists})


@app.route("/api/citizen/register", methods=["POST"])
def register_citizen():
    data = request.get_json()
    if data["dob"] > str(date.today()):
        return jsonify({"message": "Date of birth cannot be in the future"}), 400
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO CITIZEN
            (NationalIDNo, FirstName, LastName, OtherName, DOB, Gender,
             CountryOfBirth, Nationality, Email, Phone, Address)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
            (
                data["nationalIdNo"],
                data["firstName"],
                data["lastName"],
                data.get("otherName"),
                data["dob"],
                data["gender"],
                data["countryOfBirth"],
                data["nationality"],
                data["email"],
                data["phone"],
                data["address"],
            ),
        )
        db.commit()
        db.close()
        return jsonify({"message": "Citizen registered successfully"}), 201
    except mysql.connector.IntegrityError:
        return jsonify({"message": "National ID or email already exists"}), 409
    except Exception as e:
        return jsonify({"message": str(e)}), 500


# ══════════════════════════════════════════════════════════════
# PASSPORT
# ══════════════════════════════════════════════════════════════
@app.route("/api/passport/verify")
def verify_passport():
    national_id = request.args.get("nationalId")
    passport_no = request.args.get("passportNo")
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT p.PassportNo, c.NationalIDNo, CONCAT(c.FirstName, ' ', c.LastName), 
                    p.IssueDate, p.ExpiryDate, p.PassportStatus
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
        if row["PassportStatus"] != "Active":
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


@app.route("/api/passport/apply", methods=["POST"])
def passport_apply():
    data = request.get_json()
    if data.get("applicationDate", str(date.today())) > str(date.today()):
        return jsonify({"message": "Application date cannot be in the future"}), 400
    try:
        db = get_db()
        cursor = db.cursor()

        # Auto assign first available officer
        cursor.execute("SELECT OfficerID FROM IMMIGRATION_OFFICER LIMIT 1")
        officer_row = cursor.fetchone()
        if not officer_row:
            return jsonify({"message": "No officers available to process application"}), 503
        officer_id = officer_row[0]

        cursor.execute("SELECT COUNT(*) FROM APPLICATION")
        count = cursor.fetchone()[0]
        app_id = f"APP{count + 1:04d}"
        
        cursor.execute(
            """
            INSERT INTO APPLICATION
            (ApplicationID, NationalIDNo, OfficerID, ApplicationType,
             ApplicationStatus, ApplicationDate)
            VALUES (%s, %s, %s, %s, 'Pending', %s)
        """,
            (
                app_id,
                data["nationalIdNo"],
                officer_id,
                data["applicationType"],
                str(date.today()),
            ),
        )
        db.commit()
        db.close()
        return jsonify({"message": "Application submitted", "applicationId": app_id}), 201
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/passport/applications/<national_id>")
def get_applications(national_id):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT a.ApplicationID, a.ApplicationType, a.ApplicationStatus,
                   a.ApplicationDate, p.PassportNo
            FROM APPLICATION a
            LEFT JOIN PASSPORT p ON a.ApplicationID = p.ApplicationID
            WHERE a.NationalIDNo = %s
            ORDER BY a.ApplicationDate DESC
        """,
            (national_id,),
        )
        rows = cursor.fetchall()
        db.close()
        for r in rows:
            r["ApplicationDate"] = str(r["ApplicationDate"])
        return jsonify(camel_rows(rows))
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/api/passport/pending")
def get_pending():
    officer_id = request.args.get("officerId", "")
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        query = """
            SELECT ApplicationID, NationalIDNo, ApplicationType,
                   ApplicationStatus, ApplicationDate
            FROM APPLICATION
            WHERE ApplicationStatus = 'Pending'
              AND ApplicationType IN ('New Passport', 'Renewal')
        """
        params = []
        if officer_id:
            query += " AND OfficerID = %s"
            params.append(officer_id)
        query += " ORDER BY ApplicationDate ASC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        db.close()
        for r in rows:
            r["ApplicationDate"] = str(r["ApplicationDate"])
        return jsonify(camel_rows(rows))
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/passport/process", methods=["POST"])
def process_passport():
    data = request.get_json()
    app_id = data["applicationId"]
    decision = data["decision"]  # 'approved' or 'rejected'
    reason = data.get("reason")
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Fetch application
        cursor.execute(
            """
            SELECT a.*, c.Nationality
            FROM APPLICATION a
            JOIN CITIZEN c ON a.NationalIDNo = c.NationalIDNo
            WHERE a.ApplicationID = %s
        """,
            (app_id,),
        )
        appl = cursor.fetchone()
        if not appl:
            db.close()
            return jsonify({"message": "Application not found"}), 404

        status_map = {"approved": "Approved", "rejected": "Rejected"}
        cursor.execute(
            """
            UPDATE APPLICATION
            SET ApplicationStatus = %s, RejectionReason = %s
            WHERE ApplicationID = %s
        """,
            (status_map[decision], reason, app_id),
        )

        passport_no = None

        if decision == "approved":
            # Auto-create passport record
            cursor.execute("SELECT COUNT(*) FROM PASSPORT")
            count = cursor.fetchone()["COUNT(*)"]
            passport_no = f"GH{count + 1:05d}-{str(date.today().year)[2:]}"
            issue_date = date.today()
            expiry_date = issue_date.replace(year=issue_date.year + 10)

            # Archive existing active passport for renewals
            if appl["ApplicationType"] == "Renewal":
                cursor.execute(
                    """
                    UPDATE PASSPORT SET PassportStatus = 'Expired'
                    WHERE NationalIDNo = %s AND PassportStatus = 'Active'
                """,
                    (appl["NationalIDNo"],),
                )

            cursor.execute(
                """
                INSERT INTO PASSPORT
                (PassportNo, NationalIDNo, ApplicationID, PassportType,
                 IssueDate, ExpiryDate, Nationality, IssuingOffice, PassportStatus)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Active')
            """,
                (
                    passport_no,
                    appl["NationalIDNo"],
                    app_id,
                    data.get("passportType", "Ordinary"),
                    str(issue_date),
                    str(expiry_date),
                    appl["Nationality"],
                    data.get("issuingOffice", "Head Office"),
                ),
            )

        db.commit()
        db.close()
        return jsonify(
            {
                "message": f"Application {decision}",
                "passportNo": passport_no if decision == "approved" else None,
            }
        ), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/passport/search")
def search_passports():
    q = request.args.get("q", "")
    status = request.args.get("status", "")
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        query = """
            SELECT p.PassportNo, p.NationalIDNo, p.PassportType,
                   p.IssueDate, p.ExpiryDate, p.PassportStatus,
                   c.FirstName, c.LastName
            FROM PASSPORT p
            JOIN CITIZEN c ON p.NationalIDNo = c.NationalIDNo
            WHERE (p.PassportNo LIKE %s OR p.NationalIDNo LIKE %s)
        """
        params = [f"%{q}%", f"%{q}%"]
        if status:
            query += " AND p.PassportStatus = %s"
            params.append(status.capitalize())
        query += " ORDER BY p.IssueDate DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        db.close()
        for r in rows:
            r["IssueDate"] = str(r["IssueDate"])
            r["ExpiryDate"] = str(r["ExpiryDate"])
        return jsonify(camel_rows(rows))
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/passport/revoke", methods=["POST"])
def revoke_passport():
    data = request.get_json()
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "UPDATE PASSPORT SET PassportStatus = 'Revoked' WHERE PassportNo = %s",
            (data["passportNo"],),
        )
        db.commit()
        db.close()
        return jsonify({"message": "Passport revoked"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500


# ══════════════════════════════════════════════════════════════
# VISA
# ══════════════════════════════════════════════════════════════
@app.route("/api/visa/apply", methods=["POST"])
def visa_apply():
    data = request.get_json()
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT OfficerID FROM IMMIGRATION_OFFICER LIMIT 1")
        officer_id = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM APPLICATION")
        count = cursor.fetchone()[0]
        app_id = f"APP{count + 1:04d}"
        cursor.execute("SELECT COUNT(*) FROM VISA")
        vcount = cursor.fetchone()[0]
        visa_id = f"{data['nationalIdNo'][:8]}-{vcount + 1:03d}"

        cursor.execute(
            """
            INSERT INTO APPLICATION
            (ApplicationID, NationalIDNo, OfficerID, ApplicationType, ApplicationStatus, ApplicationDate)
            VALUES (%s, %s, %s, 'Visa', 'Pending', %s)
        """,
            (app_id, data["nationalIDNo"], officer_id, str(date.today())),
        )

        cursor.execute(
            """
            INSERT INTO VISA
            (VisaID, NationalIDNo, PassportNo, ApplicationID, OfficerID,
             VisaType, VisaStatus, NumberOfEntries, DurationOfStay)
            VALUES (%s, %s, %s, %s, %s, %s, 'Pending', %s, %s)
        """,
            (
                visa_id,
                data["nationalIdNo"],
                data["passportNo"],
                app_id,
                data["officerId"],
                data["visaType"],
                data.get("numberOfEntries"),
                data.get("durationOfStay"),
            ),
        )
        db.commit()
        db.close()
        return jsonify(
            {"message": "Visa application submitted", "visaId": visa_id}
        ), 201
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/visa/citizen/<national_id>")
def get_citizen_visas(national_id):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT VisaID, VisaType, IssueDate, ExpiryDate,
                   VisaStatus, DurationOfStay, NumberOfEntries, PassportNo
            FROM VISA
            WHERE NationalIDNo = %s
            ORDER BY IssueDate DESC
        """,
            (national_id,),
        )
        rows = cursor.fetchall()
        db.close()
        for r in rows:
            if r["IssueDate"]:
                r["IssueDate"] = str(r["IssueDate"])
            if r["ExpiryDate"]:
                r["ExpiryDate"] = str(r["ExpiryDate"])
        return jsonify(camel_rows(rows))
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/visa/pending")
def get_pending_visas():
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT v.VisaID, v.NationalIDNo, v.PassportNo,
                v.VisaType, v.VisaStatus, v.NumberOfEntries,
                v.DurationOfStay, a.ApplicationID, a.ApplicationDate
                FROM VISA v
                JOIN APPLICATION a ON v.ApplicationID = a.ApplicationID
                WHERE v.VisaStatus = 'Pending'
                ORDER BY a.ApplicationDate ASC
        """)
        rows = cursor.fetchall()
        db.close()
        for r in rows:
            r["ApplicationDate"] = str(r["ApplicationDate"])
        return jsonify(camel_rows(rows))
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/visa/all")
def get_all_visas():
    q = request.args.get("q", "")
    status = request.args.get("status", "")
    vtype = request.args.get("type", "")
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        query = """
            SELECT v.VisaID, v.NationalIDNo, v.VisaType, v.VisaStatus,
                   v.IssueDate, v.ExpiryDate, v.PassportNo
            FROM VISA v WHERE (v.VisaID LIKE %s OR v.NationalIDNo LIKE %s)
        """
        params = [f"%{q}%", f"%{q}%"]
        if status:
            query += " AND v.VisaStatus = %s"
            params.append(status)
        if vtype:
            query += " AND v.VisaType = %s"
            params.append(vtype)
        query += " ORDER BY v.IssueDate DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        db.close()
        for r in rows:
            if r["IssueDate"]:
                r["IssueDate"] = str(r["IssueDate"])
            if r["ExpiryDate"]:
                r["ExpiryDate"] = str(r["ExpiryDate"])
        return jsonify(camel_rows(rows))
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/visa/process", methods=["POST"])
def process_visa():
    data = request.get_json()
    visa_id = data["visaId"]
    decision = data["decision"]
    reason = data.get("reason")
    try:
        db = get_db()
        cursor = db.cursor()
        if decision == "approved":
            issue_date = date.today()
            duration = data.get("durationOfStay", 6)
            expiry_date = issue_date.replace(
                month=issue_date.month + duration
                if issue_date.month + duration <= 12
                else ((issue_date.month + duration) % 12),
                year=issue_date.year + (issue_date.month + duration - 1) // 12,
            )
            cursor.execute(
                """
                UPDATE VISA SET VisaStatus = 'Approved',
                IssueDate = %s, ExpiryDate = %s WHERE VisaID = %s
            """,
                (str(issue_date), str(expiry_date), visa_id),
            )
        else:
            # Rejected visa must have PassportNo set to NULL (business rule)
            cursor.execute(
                """
                UPDATE VISA SET VisaStatus = 'Rejected', PassportNo = NULL
                WHERE VisaID = %s
            """,
                (visa_id,),
            )
        cursor.execute(
            """
            UPDATE APPLICATION a
            JOIN VISA v ON a.ApplicationID = v.ApplicationID
            SET a.ApplicationStatus = %s, a.RejectionReason = %s
            WHERE v.VisaID = %s
        """,
            ("Approved" if decision == "approved" else "Rejected", reason, visa_id),
        )
        db.commit()
        db.close()
        return jsonify({"message": f"Visa {decision}"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500


# ══════════════════════════════════════════════════════════════
# TRAVEL
# ══════════════════════════════════════════════════════════════
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
        return jsonify(camel_rows(rows))
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/travel/stats")
def travel_stats():
    try:
        db = get_db()
        cursor = db.cursor()
        today = date.today()
        first = today.replace(day=1)
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
            "SELECT COUNT(*) FROM TRAVEL_RECORD WHERE TravelDate >= %s", (first,)
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
        ee = request.args.get("entryOrExit")
        if ee:
            query += " AND t.EntryOrExit = %s"
            params.append(ee)
        mode = request.args.get("mode")
        if mode:
            query += " AND t.ModeOfTravel = %s"
            params.append(mode)
        df = request.args.get("from")
        if df:
            query += " AND t.TravelDate >= %s"
            params.append(df)
        dt = request.args.get("to")
        if dt:
            query += " AND t.TravelDate <= %s"
            params.append(dt)
        query += " ORDER BY t.TravelDate DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        db.close()
        for r in rows:
            r["TravelDate"] = str(r["TravelDate"])
        return jsonify(camel_rows(rows))
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/travel/log", methods=["POST"])
def log_travel():
    data = request.get_json()
    if data["travelDate"] > str(date.today()):
        return jsonify({"message": "Travel date cannot be in the future"}), 400
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM TRAVEL_RECORD")
        count = cursor.fetchone()[0]
        travel_id = f"TRV{count + 1:04d}"
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


# ══════════════════════════════════════════════════════════════
# OFFICERS
# ══════════════════════════════════════════════════════════════
@app.route("/api/officers/stats")
def officer_stats():
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM IMMIGRATION_OFFICER")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(DISTINCT BorderPostID) FROM IMMIGRATION_OFFICER")
        posts = cursor.fetchone()[0]
        db.close()
        return jsonify({"total": total, "posts": posts})
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/officers")
def get_officers():
    q = request.args.get("q", "")
    post = request.args.get("post", "")
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        query = """
            SELECT o.OfficerID, o.OfficerFirstName, o.OfficerLastName,
                   o.BorderPostID, b.BorderPostName, b.BorderType
            FROM IMMIGRATION_OFFICER o
            JOIN BORDER_POST b ON o.BorderPostID = b.BorderPostID
            WHERE (o.OfficerID LIKE %s OR o.OfficerLastName LIKE %s
                   OR o.OfficerFirstName LIKE %s)
        """
        params = [f"%{q}%", f"%{q}%", f"%{q}%"]
        if post:
            query += " AND o.BorderPostID = %s"
            params.append(post)
        query += " ORDER BY o.OfficerLastName ASC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        db.close()
        return jsonify(camel_rows(rows))
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/officers/register", methods=["POST"])
def register_officer():
    data = request.get_json()
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM IMMIGRATION_OFFICER")
        count = cursor.fetchone()[0]
        officer_id = f"OFF{count + 1:04d}"
        cursor.execute(
            """
            INSERT INTO IMMIGRATION_OFFICER
            (OfficerID, OfficerFirstName, OfficerLastName, BorderPostID)
            VALUES (%s, %s, %s, %s)
        """,
            (officer_id, data["officerFirstName"], data["officerLastName"], data["borderPostID"]),
        )
        db.commit()
        db.close()
        return jsonify({"message": "Officer registered", "officerId": officer_id}), 201
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/officers/reassign", methods=["POST"])
def reassign_officer():
    data = request.get_json()
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "UPDATE IMMIGRATION_OFFICER SET BorderPostID = %s WHERE OfficerID = %s",
            (data["borderPostID"], data["officerID"]),
        )
        db.commit()
        db.close()
        return jsonify({"message": "Officer reassigned"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500


# ══════════════════════════════════════════════════════════════
# BORDER
# ══════════════════════════════════════════════════════════════
@app.route("/api/border/stats")
def border_stats():
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM BORDER_POST")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM BORDER_POST WHERE BorderType = 'Airport'")
        airports = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM BORDER_POST WHERE BorderType = 'Land'")
        land = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM BORDER_POST WHERE BorderType = 'Sea'")
        sea = cursor.fetchone()[0]
        db.close()
        return jsonify({"total": total, "airports": airports, "land": land, "sea": sea})
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/border/posts")
def get_border_posts():
    btype = request.args.get("type", "")
    country = request.args.get("country", "")
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        query = """
            SELECT b.BorderPostID, b.BorderPostName, b.BorderType,
                   b.CountryCode, c.CountryName
            FROM BORDER_POST b
            JOIN COUNTRY c ON b.CountryCode = c.CountryCode
            WHERE 1=1
        """
        params = []
        if btype:
            query += " AND b.BorderType = %s"
            params.append(btype)
        if country:
            query += " AND b.CountryCode = %s"
            params.append(country)
        query += " ORDER BY b.BorderPostName ASC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        db.close()
        return jsonify(camel_rows(rows))
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/border/deployments")
def get_deployments():
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT b.BorderPostID, b.BorderPostName, b.BorderType,
                   COUNT(o.OfficerID) AS officerCount
            FROM BORDER_POST b
            LEFT JOIN IMMIGRATION_OFFICER o ON b.BorderPostID = o.BorderPostID
            GROUP BY b.BorderPostID, b.BorderPostName, b.BorderType
            ORDER BY officerCount DESC
        """)
        rows = cursor.fetchall()
        db.close()
        return jsonify(camel_rows(rows))
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/border/register", methods=["POST"])
def register_border_post():
    data = request.get_json()
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM BORDER_POST")
        count = cursor.fetchone()[0]
        post_id = f"{data['countryCode']}{count + 1:04d}"
        cursor.execute(
            """
            INSERT INTO BORDER_POST (BorderPostID, BorderPostName, CountryCode, BorderType)
            VALUES (%s, %s, %s, %s)
        """,
            (post_id, data["borderPostName"], data["countryCode"], data["borderType"]),
        )
        db.commit()
        db.close()
        return jsonify(
            {"message": "Border post registered", "borderPostId": post_id}
        ), 201
    except Exception as e:
        return jsonify({"message": str(e)}), 500


# ══════════════════════════════════════════════════════════════
# PAYMENT
# ══════════════════════════════════════════════════════════════
@app.route("/api/payment/make", methods=["POST"])
def make_payment():
    data = request.get_json()
    if data.get("paymentDate", str(date.today())) > str(date.today()):
        return jsonify({"message": "Payment date cannot be in the future"}), 400
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM PAYMENT")
        count = cursor.fetchone()[0]
        ref_no = f"PAY{count + 1:04d}"
        cursor.execute(
            """
            INSERT INTO PAYMENT
            (PaymentRefNo, ApplicationID, NationalIDNo, Amount,
             PaymentDate, PaymentMethod, PaymentFor, PaymentStatus)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'Confirmed')
        """,
            (
                ref_no,
                data["applicationId"],
                data["nationalIdNo"],
                data["amount"],
                str(date.today()),
                data["paymentMethod"],
                data["paymentFor"],
            ),
        )
        # Move application to Processing once paid
        cursor.execute(
            """
            UPDATE APPLICATION SET ApplicationStatus = 'Processing'
            WHERE ApplicationID = %s AND ApplicationStatus = 'Pending'
        """,
            (data["applicationId"],),
        )
        db.commit()
        db.close()
        return jsonify({"message": "Payment confirmed", "paymentRefNo": ref_no}), 201
    except Exception as e:
        return jsonify({"message": str(e)}), 500


# ══════════════════════════════════════════════════════════════
# APPOINTMENT
# ══════════════════════════════════════════════════════════════
@app.route("/api/appointment/book", methods=["POST"])
def book_appointment():
    data = request.get_json()
    if data["appointmentDate"] < str(date.today()):
        return jsonify({"message": "Scheduled appointments cannot be in the past"}), 400
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM APPOINTMENT")
        count = cursor.fetchone()[0]
        apt_id = f"APT{count + 1:04d}"
        cursor.execute(
            """
            INSERT INTO APPOINTMENT
            (AppointmentID, ApplicationID, NationalIDNo, BorderPostID,
             AppointmentDate, AppointmentStatus)
            VALUES (%s, %s, %s, %s, %s, 'Scheduled')
        """,
            (
                apt_id,
                data["applicationId"],
                data["nationalIdNo"],
                data["borderPostId"],
                data["appointmentDate"],
            ),
        )
        db.commit()
        db.close()
        return jsonify({"message": "Appointment booked", "appointmentId": apt_id}), 201
    except mysql.connector.IntegrityError:
        return jsonify(
            {"message": "An appointment already exists for this application"}
        ), 409
    except Exception as e:
        return jsonify({"message": str(e)}), 500


# ══════════════════════════════════════════════════════════════
# VERIFICATION
# ══════════════════════════════════════════════════════════════
@app.route("/api/verify/passport")
def verify_passport_doc():
    passport_no = request.args.get("passportNo")
    national_id = request.args.get("nationalId")
    officer_id = request.args.get("officerId")
    if not passport_no or not officer_id:
        return jsonify(
            {"valid": False, "message": "Passport number and Officer ID required"}
        ), 400
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        query = """
            SELECT p.PassportNo, p.NationalIDNo, p.PassportType, p.IssueDate,
                   p.ExpiryDate, p.Nationality, p.IssuingOffice, p.PassportStatus,
                   CONCAT(c.FirstName, ' ', c.LastName) AS CitizenName
            FROM PASSPORT p
            JOIN CITIZEN c ON p.NationalIDNo = c.NationalIDNo
            WHERE p.PassportNo = %s
        """
        params = [passport_no]
        if national_id:
            query += " AND p.NationalIDNo = %s"
            params.append(national_id)
        cursor.execute(query, params)
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"valid": False, "message": "Passport not found"})
        if row["PassportStatus"] != "Active":
            db.close()
            return jsonify(
                {
                    "valid": False,
                    "message": f"Passport is {row['PassportStatus']}",
                    "passport": {
                        "passportNo": row["PassportNo"],
                        "citizenName": row["CitizenName"],
                        "nationalIdNo": row["NationalIDNo"],
                        "passportType": row["PassportType"],
                        "issueDate": str(row["IssueDate"]),
                        "expiryDate": str(row["ExpiryDate"]),
                        "nationality": row["Nationality"],
                        "issuingOffice": row["IssuingOffice"],
                        "status": row["PassportStatus"],
                    },
                }
            )
        expiring_soon = row["ExpiryDate"] <= (date.today() + timedelta(days=180))
        cursor.execute(
            """
            SELECT DepartureCountry, ArrivalCountry, TravelDate
            FROM TRAVEL_RECORD WHERE PassportNo = %s
            ORDER BY TravelDate DESC LIMIT 3
        """,
            (passport_no,),
        )
        recent = cursor.fetchall()
        for t in recent:
            t["TravelDate"] = str(t["TravelDate"])
        log_audit(cursor, officer_id, "Viewed", "PASSPORT", passport_no)
        db.commit()
        db.close()
        return jsonify(
            {
                "valid": True,
                "expiringSoon": expiring_soon,
                "message": "Expiring within 6 months — renewal recommended"
                if expiring_soon
                else "Passport is valid",
                "passport": {
                    "passportNo": row["PassportNo"],
                    "citizenName": row["CitizenName"],
                    "nationalIdNo": row["NationalIDNo"],
                    "passportType": row["PassportType"],
                    "issueDate": str(row["IssueDate"]),
                    "expiryDate": str(row["ExpiryDate"]),
                    "nationality": row["Nationality"],
                    "issuingOffice": row["IssuingOffice"],
                    "status": row["PassportStatus"],
                },
                "recentTravel": recent,
            }
        )
    except Exception as e:
        return jsonify({"valid": False, "message": str(e)}), 500


@app.route("/api/verify/visa")
def verify_visa_doc():
    visa_id = request.args.get("visaId")
    passport_no = request.args.get("passportNo")
    officer_id = request.args.get("officerId")
    if not visa_id or not officer_id:
        return jsonify(
            {"valid": False, "message": "Visa ID and Officer ID required"}
        ), 400
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        query = """
            SELECT v.VisaID, v.PassportNo, v.VisaType, v.IssueDate, v.ExpiryDate,
                   v.VisaStatus, v.DurationOfStay, v.NumberOfEntries,
                   CONCAT(c.FirstName, ' ', c.LastName) AS CitizenName
            FROM VISA v
            JOIN CITIZEN c ON v.NationalIDNo = c.NationalIDNo
            WHERE v.VisaID = %s
        """
        params = [visa_id]
        if passport_no:
            query += " AND v.PassportNo = %s"
            params.append(passport_no)
        cursor.execute(query, params)
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"valid": False, "message": "Visa not found"})
        log_audit(cursor, officer_id, "Viewed", "VISA", visa_id)
        db.commit()
        db.close()
        return jsonify(
            {
                "valid": row["VisaStatus"] == "Approved",
                "message": "Visa is valid"
                if row["VisaStatus"] == "Approved"
                else f"Visa is {row['VisaStatus'].lower()}",
                "visa": {
                    "visaId": row["VisaID"],
                    "citizenName": row["CitizenName"],
                    "passportNo": row["PassportNo"],
                    "visaType": row["VisaType"],
                    "issueDate": str(row["IssueDate"]) if row["IssueDate"] else None,
                    "expiryDate": str(row["ExpiryDate"]) if row["ExpiryDate"] else None,
                    "status": row["VisaStatus"],
                    "durationOfStay": row["DurationOfStay"],
                    "numberOfEntries": row["NumberOfEntries"],
                },
            }
        )
    except Exception as e:
        return jsonify({"valid": False, "message": str(e)}), 500


@app.route("/api/verify/citizen")
def verify_citizen_doc():
    national_id = request.args.get("nationalId")
    officer_id = request.args.get("officerId")
    if not national_id or not officer_id:
        return jsonify(
            {"found": False, "message": "National ID and Officer ID required"}
        ), 400
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT NationalIDNo, FirstName, LastName, OtherName,
                   DOB, Gender, Nationality, CountryOfBirth, Email, Phone
            FROM CITIZEN WHERE NationalIDNo = %s
        """,
            (national_id,),
        )
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"found": False, "message": "No citizen record found"})
        cursor.execute(
            """
            SELECT PassportNo, PassportType, PassportStatus, ExpiryDate
            FROM PASSPORT WHERE NationalIDNo = %s ORDER BY IssueDate DESC
        """,
            (national_id,),
        )
        passports = cursor.fetchall()
        for p in passports:
            p["ExpiryDate"] = str(p["ExpiryDate"])
        active_count = sum(1 for p in passports if p["PassportStatus"] == "Active")
        log_audit(cursor, officer_id, "Viewed", "CITIZEN", national_id)
        db.commit()
        db.close()
        other = f" {row['OtherName']}" if row["OtherName"] else ""
        return jsonify(
            {
                "found": True,
                "message": "Citizen record found",
                "citizen": {
                    "nationalIdNo": row["NationalIDNo"],
                    "fullName": f"{row['FirstName']}{other} {row['LastName']}",
                    "dob": str(row["DOB"]),
                    "gender": row["Gender"],
                    "nationality": row["Nationality"],
                    "countryOfBirth": row["CountryOfBirth"],
                    "email": row["Email"],
                    "phone": row["Phone"],
                    "activePassports": active_count,
                },
                "passports": passports,
            }
        )
    except Exception as e:
        return jsonify({"found": False, "message": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
