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

|        Entity       |                        Description                     |
|---------------------|--------------------------------------------------------|
|             CITIZEN |                Core identity record for all applicants |
|            PASSPORT |             Issued travel documents linked to citizens |
|                VISA |            Entry permissions stamped against passports |
|         APPLICATION |         Tracks requests for passports, visas, renewals |
| IMMIGRATION OFFICER |    Staff who process applications and border crossings |
|         BORDER POST |          Physical crossing points (airport, land, sea) |
|       TRAVEL RECORD |                        Logs every entry and exit event |
|             PAYMENT |                              Fees paid per application |
|         APPOINTMENT |             Scheduled visits for document verification |
|             COUNTRY | Reference table for all nationalities and destinations |
|           AUDIT LOG |                Immutable record of all officer actions |

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
- **Language:** SQL (DDL, DML, triggers, views, stored procedures)

---

## Setup

```sql
-- Create and select the database
CREATE DATABASE npims;
USE npims;

-- Run schema file
SOURCE schema.sql;

-- Populate with sample data
SOURCE seed.sql;
```

---

## Team

|             Name         | Student ID |
|--------------------------|------------|
| Prince Nii Adjetey Adjei |   07592028 |
|     Oluwademilade Subair |   58742028 |
|    Ebow Essilfie Quaicoe |   88872028 |
|           Filbert Jethro |   19502028 |
