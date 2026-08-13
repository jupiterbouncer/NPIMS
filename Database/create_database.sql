-- ============================================================
-- NPIMS: Physical design for the full DDL
-- ============================================================

CREATE DATABASE IF NOT EXISTS NPIMS
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE NPIMS;

-- Drop tables in safe order (children before parents)
DROP TABLE IF EXISTS AUDIT_LOG;
DROP TABLE IF EXISTS TRAVEL_RECORD;
DROP TABLE IF EXISTS VISA;
DROP TABLE IF EXISTS PASSPORT;
DROP TABLE IF EXISTS APPOINTMENT;
DROP TABLE IF EXISTS PAYMENT;
DROP TABLE IF EXISTS APPLICATION;
DROP TABLE IF EXISTS IMMIGRATION_OFFICER;
DROP TABLE IF EXISTS BORDER_POST;
DROP TABLE IF EXISTS CITIZEN;
DROP TABLE IF EXISTS COUNTRY;

-- Drop triggers if re-running
DROP TRIGGER IF EXISTS trg_citizen_dob_insert;
DROP TRIGGER IF EXISTS trg_citizen_dob_update;
DROP TRIGGER IF EXISTS trg_travel_date_insert;
DROP TRIGGER IF EXISTS trg_travel_date_update;