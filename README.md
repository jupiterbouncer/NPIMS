# National Passport & Immigration Management System (NPIMS)

A relational database system designed to manage passport applications,
visa requests, border crossings, and immigration records for national
immigration agencies.

Built as a final project for Database Systems CS323_C.

---

## Overview

Immigration agencies process thousands of passport applications, visa
requests, renewals, and border entries daily. NPIMS provides a structured,
secure, and efficient database solution to manage these operations across
citizens, officers, border posts, and government offices.

---

## Features

- Citizen registration and identity management
- Passport application, issuance, and renewal tracking
- Visa processing linked to valid passport records
- Border crossing entry and exit logging
- Payment tracking per application
- Appointment scheduling for document verification
- Country-level visa requirement management
- Audit logging for all sensitive officer actions
- Role-based data access via user privileges

---

## Entities

| Entity              | Description                                            |
| ------------------- | ------------------------------------------------------ |
| CITIZEN             | Core identity record for all applicants                |
| PASSPORT            | Issued travel documents linked to citizens             |
| VISA                | Entry permissions stamped against passports            |
| APPLICATION         | Tracks requests for passports, visas, renewals         |
| IMMIGRATION OFFICER | Staff who process applications and border crossings    |
| BORDER POST         | Physical crossing points (airport, land, sea)          |
| TRAVEL RECORD       | Logs every entry and exit event                        |
| PAYMENT             | Fees paid per application                              |
| APPOINTMENT         | Scheduled visits for document verification             |
| COUNTRY             | Reference table for all nationalities and destinations |
| AUDIT LOG           | Immutable record of all officer actions                |

---

## Business Rules (Key)

- A citizen can hold only ONE active passport at a time
- A visa cannot outlive the passport it is stamped in
- A travel record cannot be created with an expired or revoked passport
- Payment must be confirmed before an application moves to processing
- All officer actions on sensitive records generate an audit log entry
- Countries are deactivated, never deleted

---

## Tech Stack

- **Database:** MariaDB
- **Language:** Python, SQL (DDL, DML, triggers, views, stored procedures)
- **Frontend:** HTML, JavaScript, Flask-CORS

---

```text
NPIMS/
│
├── backend/
│   └── logic.py
│
├── database/
│   ├── schema.sql
│   ├── seeds.sql
│   └── advanced_functions.sql
│
├── frontend/
│   └── pages/
│       ├── citizen.html
│       ├── passport.html
│       ├── visa.html
│       ├── officers.html
│       ├── travel.html
│       ├── border.html
│       └── verification.html
│
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd NPIMS
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it:

```bash
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file in the project root.

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=npims
```

Please do not commit your actual `.env` file.

## Database Setup

```sql
-- Create and select the database
CREATE DATABASE npims;
USE npims;

-- Run schema file
SOURCE npims_schema.sql;

-- Populate with sample data
SOURCE npims_seed_data.sql;

-- Advanced function
SOURCE npims_advanced_func.sql
```

The schema creates the required tables and relationships, the seed file populates the database with test data, and the advanced-functions file contains additional database functionality such as procedures, triggers, views, or related SQL features.

---

## Running the Application

From the project root:

```bash
python backend/logic.py
```

Then open the local Flask address shown in the terminal, typically:

```text
http://127.0.0.1:5000
```

---

## Reproducibility

You should only need to:

1. Clone the repository.
2. Create and activate a virtual environment.
3. Install `requirements.txt`.
4. Copy `.env.example` to `.env` and provide your MariaDB credentials.
5. Run the SQL files in the documented order.
6. Run `python backend/logic.py`.

No source-code changes should be required for another user to run the project.


## Team

| Name                     | Student ID |
| ------------------------ | ---------- |
| Prince Nii Adjetey Adjei | 07592028   |
| Oluwademilade Subair     | 58742028   |
| Ebow Essilfie Quaicoe    | 88872028   |
| Filbert Jethro           | 19502028   |
