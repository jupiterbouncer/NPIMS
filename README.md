# National Passport & Immigration Management System (NPIMS)

NPIMS is a database-backed immigration management system for citizen records, passport applications, visa processing, border crossings, officer deployments, verification, payments, and simple operational reports.

This project was built for the Database Systems CS323 final project.

## Project Structure

```text
NPIMS/
+-- Application/
|   +-- backend/
|   |   +-- logic.py
|   +-- frontend/
|       +-- citizen.html
|       +-- passport.html
|       +-- visa.html
|       +-- travel.html
|       +-- verification.html
|       +-- officers.html
|       +-- border.html
+-- Database/
|   +-- create_database.sql
|   +-- create_tables.sql
|   +-- insert_data.sql
|   +-- views.sql
|   +-- procedures.sql
|   +-- triggers.sql
|   +-- queries.sql
|   +-- security.sql
+-- Video/
|   +-- project_demo.mp4
+-- requirements.txt
+-- README.md
```

## Tech Stack

- **Backend:** Python, Flask, Flask-CORS
- **Database:** MySQL/MariaDB
- **Frontend:** HTML, CSS, JavaScript
- **Database features:** tables, constraints, indexes, triggers, views, stored procedures, functions, sample queries, and role/security scripts

## Main Features

- Citizen registration and citizen lookup
- Passport application, renewal, approval, rejection, revocation, and status tracking
- Visa application and officer processing
- Border crossing logging with passport validation
- Border post registration and officer deployment management
- Officer reassignment
- Passport, visa, and citizen verification screens
- Payment submission for passport-related applications
- Report cards for passport status summaries and border crossing activity
- Exposed database view usage through the border crossing report
- Exposed stored function usage through the passport status lookup

## Key Database Tables

| Table | Purpose |
| --- | --- |
| `COUNTRY` | Country and visa requirement reference data |
| `CITIZEN` | Citizen identity records |
| `BORDER_POST` | Airport, land, and sea border posts |
| `IMMIGRATION_OFFICER` | Officers assigned to border posts |
| `APPLICATION` | Passport, renewal, and visa applications |
| `PAYMENT` | Payments linked to applications |
| `APPOINTMENT` | Appointment records |
| `PASSPORT` | Issued passport records |
| `VISA` | Visa records linked to citizens/passports |
| `TRAVEL_RECORD` | Entry and exit travel logs |
| `AUDIT_LOG` | Audit records for sensitive operations |

## Database Setup

Create the database and load the SQL files in this order:

```sql
SOURCE Database/create_database.sql;
SOURCE Database/create_tables.sql;
SOURCE Database/insert_data.sql;
SOURCE Database/views.sql;
SOURCE Database/procedures.sql;
SOURCE Database/triggers.sql;
```

Optional supporting scripts:

```sql
SOURCE Database/queries.sql;
SOURCE Database/security.sql;
```

`queries.sql` contains sample/reporting queries. `security.sql` defines roles, users, and grants, so it may require an administrative database account.

## Environment Variables

Create a `.env` file in the project root:

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=npims
```

The backend defaults to these values if a variable is missing, except `DB_PASSWORD`, which defaults to an empty string.

## Running the Application

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Start the Flask backend from the project root:

```bash
python Application/backend/logic.py
```

Open the app in a browser:

```text
http://127.0.0.1:5000
```

The root route opens `citizen.html`. Other pages are served from `Application/frontend`, for example:

```text
http://127.0.0.1:5000/passport.html
http://127.0.0.1:5000/visa.html
http://127.0.0.1:5000/border.html
```

## Useful Demo IDs

Seeded National IDs use the format `GH000001`, `GH000002`, and so on.

Seeded Officer IDs use the format `OF00001`, `OF00002`, and so on.

Seeded Border Post IDs use the format `BP00001`, `BP00002`, and so on.

## Relevant API Areas

- `/api/citizen/*`
- `/api/passport/*`
- `/api/visa/*`
- `/api/travel/*`
- `/api/officers/*`
- `/api/border/*`
- `/api/verify/*`
- `/api/reports/*`
- `/api/payment/make`
- `/api/appointment/book`

## Notes

- The passport officer report uses `/api/reports/passport-status-summary`.
- The passport stored-function lookup uses `fn_PassportStatus`.
- The border crossing report uses `vw_BorderPostActivity` when the view exists, with a backend fallback query if the view has not been loaded yet.
- Payments update pending passport-related applications to `Processing`.
- The app is a course project demo, not a production authentication system.

## Team

| Name | Student ID |
| --- | --- |
| Prince Nii Adjetey Adjei | 07592028 |
| Oluwademilade Subair | 58742028 |
| Ebow Essilfie Quaicoe | 88872028 |
| Filbert Jethro | 19502028 |
