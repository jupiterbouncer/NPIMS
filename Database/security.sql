USE NPIMS;

-- ============================================================
-- 1. CREATE ROLES
-- ============================================================

CREATE ROLE IF NOT EXISTS immigration_officer;
CREATE ROLE IF NOT EXISTS border_officer;
CREATE ROLE IF NOT EXISTS finance_officer;
CREATE ROLE IF NOT EXISTS auditor;
CREATE ROLE IF NOT EXISTS npims_admin;


-- ============================================================
-- 2. IMMIGRATION OFFICER PRIVILEGES
-- ============================================================

GRANT SELECT, INSERT, UPDATE
ON NPIMS.APPLICATION
TO immigration_officer;

GRANT SELECT, INSERT, UPDATE
ON NPIMS.PASSPORT
TO immigration_officer;

GRANT SELECT, INSERT, UPDATE
ON NPIMS.VISA
TO immigration_officer;

GRANT SELECT, INSERT, UPDATE
ON NPIMS.APPOINTMENT
TO immigration_officer;

GRANT SELECT, UPDATE
ON NPIMS.CITIZEN
TO immigration_officer;

GRANT SELECT
ON NPIMS.TRAVEL_RECORD
TO immigration_officer;

GRANT SELECT
ON NPIMS.PAYMENT
TO immigration_officer;

GRANT SELECT
ON NPIMS.COUNTRY
TO immigration_officer;

GRANT SELECT
ON NPIMS.BORDER_POST
TO immigration_officer;


-- ============================================================
-- 3. BORDER OFFICER PRIVILEGES
-- ============================================================

GRANT SELECT, INSERT
ON NPIMS.TRAVEL_RECORD
TO border_officer;

GRANT SELECT
ON NPIMS.CITIZEN
TO border_officer;

GRANT SELECT
ON NPIMS.APPLICATION
TO border_officer;

GRANT SELECT
ON NPIMS.PASSPORT
TO border_officer;

GRANT SELECT
ON NPIMS.VISA
TO border_officer;

GRANT SELECT
ON NPIMS.APPOINTMENT
TO border_officer;

GRANT SELECT
ON NPIMS.COUNTRY
TO border_officer;

GRANT SELECT
ON NPIMS.BORDER_POST
TO border_officer;


-- ============================================================
-- 4. FINANCE OFFICER PRIVILEGES
-- ============================================================

GRANT SELECT, INSERT, UPDATE
ON NPIMS.PAYMENT
TO finance_officer;

GRANT SELECT
ON NPIMS.APPLICATION
TO finance_officer;

GRANT SELECT
ON NPIMS.CITIZEN
TO finance_officer;


-- ============================================================
-- 5. AUDITOR PRIVILEGES
-- Read-only access to the entire NPIMS database
-- ============================================================

GRANT SELECT
ON NPIMS.*
TO auditor;


-- ============================================================
-- 6. NPIMS ADMIN PRIVILEGES
-- Full access to NPIMS only
-- ============================================================

GRANT ALL PRIVILEGES
ON NPIMS.*
TO npims_admin;


-- ============================================================
-- 7. CREATE SAMPLE USER ACCOUNTS
-- ============================================================

CREATE USER IF NOT EXISTS 'immigration1'@'localhost'
IDENTIFIED BY 'Imm123!';

CREATE USER IF NOT EXISTS 'border1'@'localhost'
IDENTIFIED BY 'Border123!';

CREATE USER IF NOT EXISTS 'finance1'@'localhost'
IDENTIFIED BY 'Finance123!';

CREATE USER IF NOT EXISTS 'auditor1'@'localhost'
IDENTIFIED BY 'Audit123!';

CREATE USER IF NOT EXISTS 'npimsadmin'@'localhost'
IDENTIFIED BY 'Admin123!';


-- ============================================================
-- 8. ASSIGN ROLES TO USERS
-- ============================================================

GRANT immigration_officer
TO 'immigration1'@'localhost';

GRANT border_officer
TO 'border1'@'localhost';

GRANT finance_officer
TO 'finance1'@'localhost';

GRANT auditor
TO 'auditor1'@'localhost';

GRANT npims_admin
TO 'npimsadmin'@'localhost';


-- ============================================================
-- 9. SET DEFAULT ROLES
-- Makes the role active automatically after login
-- ============================================================

SET DEFAULT ROLE immigration_officer
FOR 'immigration1'@'localhost';

SET DEFAULT ROLE border_officer
FOR 'border1'@'localhost';

SET DEFAULT ROLE finance_officer
FOR 'finance1'@'localhost';

SET DEFAULT ROLE auditor
FOR 'auditor1'@'localhost';

SET DEFAULT ROLE npims_admin
FOR 'npimsadmin'@'localhost';


-- ============================================================
-- 10. VERIFY ROLE PRIVILEGES
-- ============================================================

SHOW GRANTS FOR immigration_officer;
SHOW GRANTS FOR border_officer;
SHOW GRANTS FOR finance_officer;
SHOW GRANTS FOR auditor;
SHOW GRANTS FOR npims_admin;


-- ============================================================
-- 11. VERIFY USER ROLE ASSIGNMENTS
-- ============================================================

SHOW GRANTS FOR 'immigration1'@'localhost';
SHOW GRANTS FOR 'border1'@'localhost';
SHOW GRANTS FOR 'finance1'@'localhost';
SHOW GRANTS FOR 'auditor1'@'localhost';
SHOW GRANTS FOR 'npimsadmin'@'localhost';