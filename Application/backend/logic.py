import os
import re
import calendar
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
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend"
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

def officer_exists(cursor, officer_id):
    cursor.execute(
        "SELECT OfficerID FROM IMMIGRATION_OFFICER WHERE OfficerID = %s",
        (officer_id,),
    )
    return cursor.fetchone() is not None

def add_months(start_date, months):
    month_index = start_date.month - 1 + months
    year = start_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start_date.day, calendar.monthrange(year, month)[1])
    return start_date.replace(year=year, month=month, day=day)

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

@app.route("/api/border-posts")
def get_border_posts_simple():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT BorderPostID, BorderPostName, CountryCode
        FROM BORDER_POST
        ORDER BY BorderPostName
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
    data = request.get_json() or {}
    required = [
        "nationalIdNo",
        "firstName",
        "lastName",
        "dob",
        "gender",
        "countryOfBirth",
        "nationality",
        "email",
        "phone",
        "address",
    ]
    missing = [field for field in required if not str(data.get(field, "")).strip()]
    if missing:
        return jsonify({"message": f"Missing required fields: {', '.join(missing)}"}), 400
    data["nationalIdNo"] = data["nationalIdNo"].strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{8}", data["nationalIdNo"]):
        return jsonify({"message": "National ID must be exactly 8 letters/numbers"}), 400
    if data["gender"] not in ("Male", "Female"):
        return jsonify({"message": "Gender must be Male or Female"}), 400
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", data["email"].strip()):
        return jsonify({"message": "A valid email address is required"}), 400
    try:
        dob = date.fromisoformat(data["dob"])
    except ValueError:
        return jsonify({"message": "Date of birth must be a valid YYYY-MM-DD date"}), 400
    if dob > date.today():
        return jsonify({"message": "Date of birth cannot be in the future"}), 400
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT CountryCode FROM COUNTRY WHERE CountryCode = %s AND IsActive = 1",
            (data["countryOfBirth"],),
        )
        if not cursor.fetchone():
            db.close()
            return jsonify({"message": "Country not found"}), 400
        cursor.execute(
            """
            INSERT INTO CITIZEN
            (NationalIDNo, FirstName, LastName, OtherName, DOB, Gender,
             CountryOfBirth, Nationality, Email, Phone, Address)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
            (
                data["nationalIdNo"].strip(),
                data["firstName"].strip(),
                data["lastName"].strip(),
                data.get("otherName", "").strip() or None,
                str(dob),
                data["gender"],
                data["countryOfBirth"],
                data["nationality"].strip(),
                data["email"].strip(),
                data["phone"].strip(),
                data["address"].strip(),
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
            SELECT p.PassportNo, c.NationalIDNo,
                c.FirstName, c.LastName,
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
    data = request.get_json() or {}
    required = ["nationalIdNo", "applicationType"]
    missing = [field for field in required if not str(data.get(field, "")).strip()]
    if missing:
        return jsonify({"message": f"Missing required fields: {', '.join(missing)}"}), 400
    data["nationalIdNo"] = data["nationalIdNo"].strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{8}", data["nationalIdNo"]):
        return jsonify({"message": "National ID must be exactly 8 letters/numbers"}), 400
    if data["applicationType"] not in ("New Passport", "Renewal"):
        return jsonify({"message": "Application type must be New Passport or Renewal"}), 400
    if data.get("applicationDate", str(date.today())) > str(date.today()):
        return jsonify({"message": "Application date cannot be in the future"}), 400
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT NationalIDNo FROM CITIZEN WHERE NationalIDNo = %s",
            (data["nationalIdNo"],),
        )
        if not cursor.fetchone():
            db.close()
            return jsonify({"message": "Citizen not found"}), 400

        if data["applicationType"] == "Renewal":
            cursor.execute(
                """
                SELECT PassportNo FROM PASSPORT
                WHERE NationalIDNo = %s AND PassportNo = %s AND PassportStatus = 'Active'
            """,
                (data["nationalIdNo"], data.get("existingPassportNo")),
            )
            if not cursor.fetchone():
                db.close()
                return jsonify({"message": "Active passport not found for renewal"}), 400

        # Auto assign first available officer
        cursor.execute("SELECT OfficerID FROM IMMIGRATION_OFFICER LIMIT 1")
        officer_row = cursor.fetchone()
        if not officer_row:
            db.close()
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
    officer_id = request.args.get("officerId", "").strip().upper()
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        if officer_id:
            if not re.fullmatch(r"OF\d{5}", officer_id):
                db.close()
                return jsonify({"message": "Officer ID must use the format OF00001"}), 400
            if not officer_exists(cursor, officer_id):
                db.close()
                return jsonify({"message": "Officer not found"}), 400
        query = """
            SELECT ApplicationID, NationalIDNo, ApplicationType,
                   ApplicationStatus, ApplicationDate
            FROM APPLICATION
            WHERE ApplicationStatus IN ('Pending', 'Processing')
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
    data = request.get_json() or {}
    app_id = data.get("applicationId")
    decision = data.get("decision")  # 'approved' or 'rejected'
    reason = data.get("reason")
    if not app_id or decision not in ("approved", "rejected"):
        return jsonify({"message": "Application ID and valid decision are required"}), 400
    if decision == "rejected" and not str(reason or "").strip():
        return jsonify({"message": "Rejection reason is required"}), 400
    passport_type = data.get("passportType", "Ordinary")
    if passport_type not in ("Ordinary", "Official"):
        return jsonify({"message": "Passport type must be Ordinary or Official"}), 400
    officer_id = str(data.get("officerId", "")).strip().upper()
    if not officer_id:
        return jsonify({"message": "Officer ID is required"}), 400
    if not re.fullmatch(r"OF\d{5}", officer_id):
        return jsonify({"message": "Officer ID must use the format OF00001"}), 400
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        if not officer_exists(cursor, officer_id):
            db.close()
            return jsonify({"message": "Officer not found"}), 400

        # Fetch application
        cursor.execute(
            """
            SELECT a.*, c.Nationality
            FROM APPLICATION a
            JOIN CITIZEN c ON a.NationalIDNo = c.NationalIDNo
            WHERE a.ApplicationID = %s
              AND a.ApplicationType IN ('New Passport', 'Renewal')
        """,
            (app_id,),
        )
        appl = cursor.fetchone()
        if not appl:
            db.close()
            return jsonify({"message": "Application not found"}), 404
        if appl["ApplicationStatus"] not in ("Pending", "Processing"):
            db.close()
            return jsonify({"message": "Only pending or processing applications can be processed"}), 400

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
                    passport_type,
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
    data = request.get_json() or {}
    if not data.get("passportNo"):
        return jsonify({"message": "Passport number is required"}), 400
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "UPDATE PASSPORT SET PassportStatus = 'Revoked' WHERE PassportNo = %s",
            (data["passportNo"],),
        )
        if cursor.rowcount == 0:
            db.close()
            return jsonify({"message": "Passport not found"}), 404
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
    data = request.get_json() or {}
    required = ["nationalIdNo", "passportNo", "visaType", "numberOfEntries", "durationOfStay"]
    missing = [field for field in required if not str(data.get(field, "")).strip()]
    if missing:
        return jsonify({"message": f"Missing required fields: {', '.join(missing)}"}), 400
    data["nationalIdNo"] = data["nationalIdNo"].strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{8}", data["nationalIdNo"]):
        return jsonify({"message": "National ID must be exactly 8 letters/numbers"}), 400
    if data["numberOfEntries"] not in ("Single", "Multiple"):
        return jsonify({"message": "Number of entries must be Single or Multiple"}), 400
    try:
        duration = int(data["durationOfStay"])
    except (TypeError, ValueError):
        return jsonify({"message": "Duration of stay must be a number"}), 400
    if duration < 1 or duration > 60:
        return jsonify({"message": "Duration of stay must be between 1 and 60 months"}), 400
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT PassportNo FROM PASSPORT
            WHERE PassportNo = %s AND NationalIDNo = %s AND PassportStatus = 'Active'
        """,
            (data["passportNo"], data["nationalIdNo"]),
        )
        if not cursor.fetchone():
            db.close()
            return jsonify({"message": "Active passport not found for this citizen"}), 400

        cursor.execute("SELECT OfficerID FROM IMMIGRATION_OFFICER LIMIT 1")

        officer_row = cursor.fetchone()
        if not officer_row:
            db.close()
            return jsonify({"message": "No officers available"}), 503
        
        officer_id = officer_row["OfficerID"]
        cursor.execute("SELECT COUNT(*) FROM APPLICATION")
        count = cursor.fetchone()["COUNT(*)"]
        app_id = f"APP{count + 1:04d}"
        cursor.execute("SELECT COUNT(*) FROM VISA")
        vcount = cursor.fetchone()["COUNT(*)"]
        visa_id = f"{data['nationalIdNo'][:8]}-{vcount + 1:03d}"

        cursor.execute(
            """
            INSERT INTO APPLICATION
            (ApplicationID, NationalIDNo, OfficerID, ApplicationType, ApplicationStatus, ApplicationDate)
            VALUES (%s, %s, %s, 'Visa', 'Pending', %s)
        """,
            (app_id, data["nationalIdNo"], officer_id, str(date.today())),
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
                officer_id,
                data["visaType"],
                data.get("numberOfEntries"),
                duration,
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
            FROM VISA v
            WHERE (v.VisaID LIKE %s OR v.NationalIDNo LIKE %s OR v.PassportNo LIKE %s)
        """
        params = [f"%{q}%", f"%{q}%", f"%{q}%"]
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
    data = request.get_json() or {}
    visa_id = data.get("visaId")
    decision = data.get("decision")
    reason = data.get("reason")
    if not visa_id or decision not in ("approved", "rejected"):
        return jsonify({"message": "Visa ID and valid decision are required"}), 400
    if decision == "rejected" and not str(reason or "").strip():
        return jsonify({"message": "Rejection reason is required"}), 400
    db = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "SELECT VisaID, ApplicationID, VisaStatus, DurationOfStay FROM VISA WHERE VisaID = %s",
            (visa_id,),
        )
        visa = cursor.fetchone()
        if not visa:
            return jsonify({"message": "Visa not found"}), 404
        if visa["VisaStatus"] != "Pending":
            return jsonify({"message": "Only pending visas can be processed"}), 400
        if decision == "approved":
            issue_date = date.today()
            duration = visa["DurationOfStay"] or 6
            expiry_date = add_months(issue_date, duration)
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
        return jsonify({"message": f"Visa {decision}"}), 200
    except Exception as e:
        if db:
            db.rollback()

        return jsonify({"message": str(e)}), 500
    finally:
        if db and db.is_connected():
            db.close()


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
    data = request.get_json() or {}
    required = [
        "nationalIdNo",
        "passportNo",
        "officerId",
        "borderPostId",
        "departureCountry",
        "arrivalCountry",
        "travelDate",
        "entryOrExit",
        "modeOfTravel",
    ]
    missing = [field for field in required if not str(data.get(field, "")).strip()]
    if missing:
        return jsonify({"message": f"Missing required fields: {', '.join(missing)}"}), 400
    try:
        travel_date = date.fromisoformat(data["travelDate"])
    except ValueError:
        return jsonify({"message": "Travel date must be a valid YYYY-MM-DD date"}), 400
    if travel_date > date.today():
        return jsonify({"message": "Travel date cannot be in the future"}), 400
    if data["entryOrExit"] not in ("entry", "exit"):
        return jsonify({"message": "Entry/exit must be either entry or exit"}), 400
    if data["modeOfTravel"] not in ("Air", "Land", "Sea"):
        return jsonify({"message": "Mode of travel must be Air, Land, or Sea"}), 400
    if data["departureCountry"] == data["arrivalCountry"]:
        return jsonify({"message": "Departure and arrival countries cannot be the same"}), 400
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT PassportStatus
            FROM PASSPORT
            WHERE PassportNo = %s AND NationalIDNo = %s
        """,
            (data["passportNo"], data["nationalIdNo"]),
        )
        passport = cursor.fetchone()
        if not passport:
            db.close()
            return jsonify({"message": "Passport not found for this citizen"}), 400
        if passport["PassportStatus"] != "Active":
            db.close()
            return jsonify({"message": f"Passport is {passport['PassportStatus']}"}), 400

        cursor.execute(
            "SELECT OfficerID FROM IMMIGRATION_OFFICER WHERE OfficerID = %s",
            (data["officerId"],),
        )
        if not cursor.fetchone():
            db.close()
            return jsonify({"message": "Officer not found"}), 400

        cursor.execute(
            "SELECT BorderPostID FROM BORDER_POST WHERE BorderPostID = %s",
            (data["borderPostId"],),
        )
        if not cursor.fetchone():
            db.close()
            return jsonify({"message": "Border post not found"}), 400

        cursor.execute("SELECT COUNT(*) FROM TRAVEL_RECORD")
        count = cursor.fetchone()["COUNT(*)"]
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
                str(travel_date),
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
        return jsonify({"total": total, "posts": posts, "unassigned": 0})
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
    data = request.get_json() or {}
    required = ["officerID", "officerFirstName", "officerLastName", "borderPostID"]
    missing = [field for field in required if not str(data.get(field, "")).strip()]
    if missing:
        return jsonify({"message": f"Missing required fields: {', '.join(missing)}"}), 400
    officer_id = data["officerID"].strip()
    if not re.fullmatch(r"OF\d{5}", officer_id):
        return jsonify({"message": "Officer ID must use the format OF00001"}), 400
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT BorderPostID FROM BORDER_POST WHERE BorderPostID = %s",
            (data["borderPostID"],),
        )
        if not cursor.fetchone():
            db.close()
            return jsonify({"message": "Border post not found"}), 400
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
    except mysql.connector.IntegrityError:
        return jsonify({"message": "Officer ID already exists"}), 409
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/officers/reassign", methods=["POST"])
def reassign_officer():
    data = request.get_json() or {}
    if not data.get("officerID") or not data.get("borderPostID"):
        return jsonify({"message": "Officer ID and border post are required"}), 400
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT BorderPostID FROM BORDER_POST WHERE BorderPostID = %s",
            (data["borderPostID"],),
        )
        if not cursor.fetchone():
            db.close()
            return jsonify({"message": "Border post not found"}), 400
        cursor.execute(
            "SELECT OfficerID FROM IMMIGRATION_OFFICER WHERE OfficerID = %s",
            (data["officerID"],),
        )
        if not cursor.fetchone():
            db.close()
            return jsonify({"message": "Officer not found"}), 404
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
                   b.CountryCode, c.CountryName,
            COUNT(DISTINCT o.OfficerID) AS OfficerCount,
            COUNT(DISTINCT t.TravelID) AS CrossingCount,
            GROUP_CONCAT(
                DISTINCT CONCAT(o.OfficerFirstName, ' ', o.OfficerLastName)
                SEPARATOR ', '
            ) AS Officers
            FROM BORDER_POST b
            JOIN COUNTRY c ON b.CountryCode = c.CountryCode
            LEFT JOIN IMMIGRATION_OFFICER o ON b.BorderPostID = o.BorderPostID
            LEFT JOIN TRAVEL_RECORD t ON b.BorderPostID = t.BorderPostID
            WHERE 1=1
        """
        params = []
        if btype:
            query += " AND b.BorderType = %s"
            params.append(btype)
        if country:
            query += " AND b.CountryCode = %s"
            params.append(country)

        query += """
            GROUP BY
                b.BorderPostID,
                b.BorderPostName,
                b.BorderType, 
                b.CountryCode,
                c.CountryName
        """
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
            SELECT o.OfficerID,
                    o.OfficerFirstName,
                    o.OfficerLastName,
                    b.BorderPostName,
                    b.BorderType,
                    b.CountryCode
            FROM IMMIGRATION_OFFICER o
            JOIN BORDER_POST b on o.BorderPostID = b.BorderPostID
            ORDER BY o.OfficerLastName, o.OfficerFirstName
        """)
        rows = cursor.fetchall()
        db.close()
        return jsonify(camel_rows(rows))
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/border/register", methods=["POST"])
def register_border_post():
    data = request.get_json() or {}
    required = ["borderPostID", "borderPostName", "countryCode", "borderType"]
    missing = [field for field in required if not str(data.get(field, "")).strip()]
    if missing:
        return jsonify({"message": f"Missing required fields: {', '.join(missing)}"}), 400
    if not re.fullmatch(r"BP\d{5}", data["borderPostID"].strip()):
        return jsonify({"message": "Border Post ID must use the format BP00001"}), 400
    if data["borderType"] not in ("Airport", "Land", "Sea"):
        return jsonify({"message": "Border type must be Airport, Land, or Sea"}), 400
    try:
        db = get_db()
        cursor = db.cursor()
        post_id = data["borderPostID"].strip()
        cursor.execute(
            "SELECT CountryCode FROM COUNTRY WHERE CountryCode = %s",
            (data["countryCode"],),
        )
        if not cursor.fetchone():
            db.close()
            return jsonify({"message": "Country not found"}), 400
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
    except mysql.connector.IntegrityError:
        return jsonify({"message": "Border post ID or name already exists"}), 409
    except Exception as e:
        return jsonify({"message": str(e)}), 500


# ══════════════════════════════════════════════════════════════
# REPORTS
# ══════════════════════════════════════════════════════════════
@app.route("/api/reports/passport-status-summary")
def passport_status_summary():
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT ApplicationStatus, COUNT(*) AS Total
            FROM APPLICATION
            WHERE ApplicationType IN ('New Passport', 'Renewal')
            GROUP BY ApplicationStatus
            ORDER BY ApplicationStatus
        """
        )
        applications = camel_rows(cursor.fetchall())
        cursor.execute(
            """
            SELECT PassportStatus, COUNT(*) AS Total
            FROM PASSPORT
            GROUP BY PassportStatus
            ORDER BY PassportStatus
        """
        )
        passports = camel_rows(cursor.fetchall())
        db.close()
        return jsonify({"applications": applications, "passports": passports})
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/reports/passport-status/<national_id>")
def passport_status_function(national_id):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "SELECT fn_PassportStatus(%s) AS PassportStatus",
            (national_id,),
        )
        row = cursor.fetchone()
        db.close()
        return jsonify(camel_rows([row])[0])
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/reports/border-crossings-summary")
def border_crossings_summary():
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        query = """
            SELECT BorderPostID, BorderPostName, BorderType, Country,
                   OfficerCount, TotalCrossings, LastCrossingDate,
                   TotalAppointments
            FROM vw_BorderPostActivity
            ORDER BY TotalCrossings DESC, BorderPostName ASC
        """
        try:
            cursor.execute(query)
        except mysql.connector.Error as err:
            if err.errno != 1146:
                raise
            cursor.execute(
                """
                SELECT
                    bp.BorderPostID,
                    bp.BorderPostName,
                    bp.BorderType,
                    co.CountryName AS Country,
                    COUNT(DISTINCT o.OfficerID) AS OfficerCount,
                    COUNT(DISTINCT t.TravelID) AS TotalCrossings,
                    MAX(t.TravelDate) AS LastCrossingDate,
                    COUNT(DISTINCT apt.AppointmentID) AS TotalAppointments
                FROM BORDER_POST bp
                JOIN COUNTRY co ON bp.CountryCode = co.CountryCode
                LEFT JOIN IMMIGRATION_OFFICER o ON bp.BorderPostID = o.BorderPostID
                LEFT JOIN TRAVEL_RECORD t ON bp.BorderPostID = t.BorderPostID
                LEFT JOIN APPOINTMENT apt ON bp.BorderPostID = apt.BorderPostID
                GROUP BY bp.BorderPostID, bp.BorderPostName, bp.BorderType, co.CountryName
                ORDER BY TotalCrossings DESC, BorderPostName ASC
            """
            )
        rows = cursor.fetchall()
        db.close()
        for r in rows:
            if r["LastCrossingDate"]:
                r["LastCrossingDate"] = str(r["LastCrossingDate"])
        return jsonify(camel_rows(rows))
    except Exception as e:
        return jsonify({"message": str(e)}), 500


# ══════════════════════════════════════════════════════════════
# PAYMENT
# ══════════════════════════════════════════════════════════════
@app.route("/api/payment/make", methods=["POST"])
def make_payment():
    data = request.get_json() or {}
    required = ["applicationId", "nationalIdNo", "amount", "paymentMethod", "paymentFor"]
    missing = [field for field in required if not str(data.get(field, "")).strip()]
    if missing:
        return jsonify({"message": f"Missing required fields: {', '.join(missing)}"}), 400
    if data["paymentMethod"] not in ("E-Transfer", "Cash Deposit"):
        return jsonify({"message": "Payment method must be E-Transfer or Cash Deposit"}), 400
    if data["paymentFor"] not in ("Passport Application", "Renewal", "Appeal"):
        return jsonify({"message": "Invalid payment purpose"}), 400
    try:
        amount = float(data["amount"])
    except (TypeError, ValueError):
        return jsonify({"message": "Amount must be a valid number"}), 400
    if amount <= 0:
        return jsonify({"message": "Amount must be greater than zero"}), 400
    if data.get("paymentDate", str(date.today())) > str(date.today()):
        return jsonify({"message": "Payment date cannot be in the future"}), 400
    db = None
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """
            SELECT ApplicationID, ApplicationType, ApplicationStatus
            FROM APPLICATION
            WHERE ApplicationID = %s AND NationalIDNo = %s
        """,
            (data["applicationId"], data["nationalIdNo"]),
        )
        app_row = cursor.fetchone()
        if not app_row:
            db.close()
            return jsonify({"message": "Application not found for this citizen"}), 404
        if app_row[2] != "Pending":
            db.close()
            return jsonify({"message": "Only pending applications can be paid for"}), 400
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
                amount,
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
        if cursor.rowcount == 0:
            db.rollback()
            db.close()
            return jsonify({"message": "Application could not be moved to Processing"}), 400
        db.commit()
        db.close()
        return jsonify({"message": "Payment confirmed", "paymentRefNo": ref_no}), 201
    except Exception as e:
        if db:
            db.rollback()
        return jsonify({"message": str(e)}), 500
    finally:
        if db and db.is_connected():
            db.close()


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
        if not officer_exists(cursor, officer_id):
            db.close()
            return jsonify({"valid": False, "message": "Officer not found"}), 400
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
        if not officer_exists(cursor, officer_id):
            db.close()
            return jsonify({"valid": False, "message": "Officer not found"}), 400
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
        if not officer_exists(cursor, officer_id):
            db.close()
            return jsonify({"found": False, "message": "Officer not found"}), 400
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
        passports = camel_rows(passports)
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
