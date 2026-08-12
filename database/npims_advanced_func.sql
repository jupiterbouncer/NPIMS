-- ============================================================
-- NPIMS: ADVANCED SQL
-- 10 Queries | 5 Views | 3 Stored Procedures | 2 UDFs
-- ============================================================

USE NPIMS;


-- ============================================================
-- ADVANCED QUERIES
-- ============================================================

-- Q1: Full citizen travel profile
-- Shows each citizen with total trips, first trip, latest trip,
-- and a breakdown of entries vs exits.
-- Demonstrates: aggregation, GROUP BY, conditional COUNT
SELECT
    c.NationalIDNo,
    CONCAT(c.FirstName, ' ', c.LastName)    AS CitizenName,
    c.Nationality,
    COUNT(t.TravelID)                        AS TotalTrips,
    MIN(t.TravelDate)                        AS FirstTrip,
    MAX(t.TravelDate)                        AS LatestTrip,
    COUNT(CASE WHEN t.EntryOrExit = 'entry' THEN 1 END) AS Entries,
    COUNT(CASE WHEN t.EntryOrExit = 'exit'  THEN 1 END) AS Exits
FROM CITIZEN c
LEFT JOIN TRAVEL_RECORD t ON c.NationalIDNo = t.NationalIDNo
GROUP BY c.NationalIDNo, c.FirstName, c.LastName, c.Nationality
ORDER BY TotalTrips DESC;


-- Q2: Passport expiry alert — passports expiring within 90 days
-- Demonstrates: DATEDIFF, filtering on computed value, JOIN
SELECT
    p.PassportNo,
    CONCAT(c.FirstName, ' ', c.LastName) AS CitizenName,
    c.Email,
    c.Phone,
    p.ExpiryDate,
    DATEDIFF(p.ExpiryDate, CURRENT_DATE)  AS DaysUntilExpiry,
    p.PassportStatus
FROM PASSPORT p
JOIN CITIZEN c ON p.NationalIDNo = c.NationalIDNo
WHERE p.PassportStatus = 'Active'
  AND p.ExpiryDate BETWEEN CURRENT_DATE AND DATE_ADD(CURRENT_DATE, INTERVAL 90 DAY)
ORDER BY DaysUntilExpiry ASC;


-- Q3: Officer workload report
-- How many applications each officer has processed and their
-- approval vs rejection rate.
-- Demonstrates: conditional aggregation, ROUND, subquery
SELECT
    o.OfficerID,
    CONCAT(o.OfficerFirstName, ' ', o.OfficerLastName) AS OfficerName,
    bp.BorderPostName,
    COUNT(a.ApplicationID)                              AS TotalProcessed,
    COUNT(CASE WHEN a.ApplicationStatus = 'Approved'  THEN 1 END) AS Approved,
    COUNT(CASE WHEN a.ApplicationStatus = 'Rejected'  THEN 1 END) AS Rejected,
    ROUND(
        COUNT(CASE WHEN a.ApplicationStatus = 'Approved' THEN 1 END)
        / NULLIF(COUNT(a.ApplicationID), 0) * 100, 2
    )                                                   AS ApprovalRatePct
FROM IMMIGRATION_OFFICER o
JOIN BORDER_POST bp ON o.BorderPostID = bp.BorderPostID
LEFT JOIN APPLICATION a ON o.OfficerID = a.OfficerID
GROUP BY o.OfficerID, o.OfficerFirstName, o.OfficerLastName, bp.BorderPostName
ORDER BY TotalProcessed DESC;


-- Q4: Citizens with multiple active passports (data integrity check)
-- Demonstrates: HAVING, subquery, business rule validation
SELECT
    c.NationalIDNo,
    CONCAT(c.FirstName, ' ', c.LastName) AS CitizenName,
    COUNT(p.PassportNo)                  AS ActivePassportCount,
    GROUP_CONCAT(p.PassportNo)           AS PassportNumbers
FROM CITIZEN c
JOIN PASSPORT p ON c.NationalIDNo = p.NationalIDNo
WHERE p.PassportStatus = 'Active'
GROUP BY c.NationalIDNo, c.FirstName, c.LastName
HAVING COUNT(p.PassportNo) > 1;


-- Q5: Monthly border crossing volume by border post
-- Demonstrates: DATE_FORMAT, GROUP BY multiple columns, ORDER BY
SELECT
    bp.BorderPostName,
    bp.BorderType,
    DATE_FORMAT(t.TravelDate, '%Y-%m')          AS Month,
    COUNT(t.TravelID)                            AS TotalCrossings,
    COUNT(CASE WHEN t.EntryOrExit = 'entry' THEN 1 END) AS Entries,
    COUNT(CASE WHEN t.EntryOrExit = 'exit'  THEN 1 END) AS Exits
FROM TRAVEL_RECORD t
JOIN BORDER_POST bp ON t.BorderPostID = bp.BorderPostID
GROUP BY bp.BorderPostName, bp.BorderType, DATE_FORMAT(t.TravelDate, '%Y-%m')
ORDER BY Month DESC, TotalCrossings DESC;


-- Q6: Visa approval rate by nationality
-- Which nationalities have the highest/lowest visa approval rates.
-- Demonstrates: JOIN chain, ROUND, NULLIF to avoid division by zero
SELECT
    c.Nationality,
    COUNT(v.VisaID)                                           AS TotalApplications,
    COUNT(CASE WHEN v.VisaStatus = 'Approved'  THEN 1 END)   AS Approved,
    COUNT(CASE WHEN v.VisaStatus = 'Rejected'  THEN 1 END)   AS Rejected,
    COUNT(CASE WHEN v.VisaStatus = 'Pending'   THEN 1 END)   AS Pending,
    ROUND(
        COUNT(CASE WHEN v.VisaStatus = 'Approved' THEN 1 END)
        / NULLIF(COUNT(v.VisaID), 0) * 100, 2
    )                                                          AS ApprovalRatePct
FROM VISA v
JOIN CITIZEN c ON v.NationalIDNo = c.NationalIDNo
GROUP BY c.Nationality
ORDER BY ApprovalRatePct DESC;


-- Q7: Revenue report — total payments by application type and month
-- Demonstrates: SUM, GROUP BY, DATE_FORMAT, ORDER BY
SELECT
    DATE_FORMAT(py.PaymentDate, '%Y-%m')  AS Month,
    py.PaymentFor                          AS ApplicationType,
    COUNT(py.PaymentRefNo)                 AS TotalPayments,
    SUM(py.Amount)                         AS TotalRevenue,
    ROUND(AVG(py.Amount), 2)               AS AveragePayment,
    MIN(py.Amount)                         AS MinPayment,
    MAX(py.Amount)                         AS MaxPayment
FROM PAYMENT py
WHERE py.PaymentStatus = 'Confirmed'
GROUP BY DATE_FORMAT(py.PaymentDate, '%Y-%m'), py.PaymentFor
ORDER BY Month DESC, TotalRevenue DESC;


-- Q8: Citizens who have travelled but have no active visa
-- Useful for compliance checking.
-- Demonstrates: LEFT JOIN, IS NULL, subquery
SELECT DISTINCT
    c.NationalIDNo,
    CONCAT(c.FirstName, ' ', c.LastName) AS CitizenName,
    c.Nationality,
    MAX(t.TravelDate)                     AS LastTravelDate
FROM CITIZEN c
JOIN TRAVEL_RECORD t ON c.NationalIDNo = t.NationalIDNo
WHERE NOT EXISTS (
    SELECT 1 FROM VISA v
    WHERE v.NationalIDNo = c.NationalIDNo
      AND v.VisaStatus = 'Approved'
      AND v.ExpiryDate >= CURRENT_DATE
)
GROUP BY c.NationalIDNo, c.FirstName, c.LastName, c.Nationality
ORDER BY LastTravelDate DESC;


-- Q9: Busiest travel routes (departure → arrival pairs)
-- Demonstrates: GROUP BY two columns, COUNT, ORDER BY
SELECT
    t.DepartureCountry,
    dep.CountryName                        AS DepartureName,
    t.ArrivalCountry,
    arr.CountryName                        AS ArrivalName,
    COUNT(t.TravelID)                      AS TotalCrossings,
    COUNT(CASE WHEN t.ModeOfTravel = 'Air'  THEN 1 END) AS ByAir,
    COUNT(CASE WHEN t.ModeOfTravel = 'Land' THEN 1 END) AS ByLand,
    COUNT(CASE WHEN t.ModeOfTravel = 'Sea'  THEN 1 END) AS BySea
FROM TRAVEL_RECORD t
JOIN COUNTRY dep ON t.DepartureCountry = dep.CountryCode
JOIN COUNTRY arr ON t.ArrivalCountry   = arr.CountryCode
GROUP BY t.DepartureCountry, dep.CountryName, t.ArrivalCountry, arr.CountryName
ORDER BY TotalCrossings DESC
LIMIT 10;


-- Q10: Full application audit trail for a single citizen
-- Shows every application, its payment, appointment, and outcome
-- (passport or visa) in one result set.
-- Demonstrates: multiple LEFT JOINs, COALESCE, CASE
SELECT
    a.ApplicationID,
    a.ApplicationType,
    a.ApplicationDate,
    a.ApplicationStatus,
    COALESCE(a.RejectionReason, '—')       AS RejectionReason,
    py.PaymentRefNo,
    py.Amount,
    py.PaymentStatus,
    apt.AppointmentDate,
    apt.AppointmentStatus,
    CASE
        WHEN a.ApplicationType IN ('New Passport','Renewal')
             THEN p.PassportNo
        ELSE NULL
    END                                    AS IssuedPassportNo,
    CASE
        WHEN a.ApplicationType = 'Visa'
             THEN v.VisaID
        ELSE NULL
    END                                    AS IssuedVisaID
FROM APPLICATION a
LEFT JOIN PAYMENT     py  ON a.ApplicationID = py.ApplicationID
LEFT JOIN APPOINTMENT apt ON a.ApplicationID = apt.ApplicationID
LEFT JOIN PASSPORT    p   ON a.ApplicationID = p.ApplicationID
LEFT JOIN VISA        v   ON a.ApplicationID = v.ApplicationID
WHERE a.NationalIDNo = 'GHA00001'   -- replace with target citizen
ORDER BY a.ApplicationDate DESC;


-- ============================================================
-- VIEWS
-- ============================================================

-- V1: Active passports with citizen details
-- Officers use this to quickly look up valid travel documents.
CREATE OR REPLACE VIEW vw_ActivePassports AS
SELECT
    p.PassportNo,
    p.NationalIDNo,
    CONCAT(c.FirstName, ' ', c.LastName) AS CitizenName,
    c.Nationality,
    p.PassportType,
    p.IssueDate,
    p.ExpiryDate,
    DATEDIFF(p.ExpiryDate, CURRENT_DATE)  AS DaysRemaining,
    p.IssuingOffice
FROM PASSPORT p
JOIN CITIZEN c ON p.NationalIDNo = c.NationalIDNo
WHERE p.PassportStatus = 'Active'
  AND p.ExpiryDate >= CURRENT_DATE;


-- V2: Pending applications queue
-- The officer dashboard loads this to populate the pending queue.
CREATE OR REPLACE VIEW vw_PendingApplications AS
SELECT
    a.ApplicationID,
    a.NationalIDNo,
    CONCAT(c.FirstName, ' ', c.LastName)  AS CitizenName,
    c.Email,
    c.Phone,
    a.ApplicationType,
    a.ApplicationDate,
    DATEDIFF(CURRENT_DATE, a.ApplicationDate) AS DaysPending,
    a.OfficerID,
    CONCAT(o.OfficerFirstName, ' ', o.OfficerLastName) AS AssignedOfficer
FROM APPLICATION a
JOIN CITIZEN            c ON a.NationalIDNo = c.NationalIDNo
JOIN IMMIGRATION_OFFICER o ON a.OfficerID   = o.OfficerID
WHERE a.ApplicationStatus = 'Pending'
ORDER BY a.ApplicationDate ASC;


-- V3: Travel summary per citizen
-- Used by the citizen-facing travel history timeline.
CREATE OR REPLACE VIEW vw_CitizenTravelSummary AS
SELECT
    t.TravelID,
    t.NationalIDNo,
    CONCAT(c.FirstName, ' ', c.LastName)  AS CitizenName,
    t.PassportNo,
    t.EntryOrExit,
    t.DepartureCountry,
    dep.CountryName                        AS DepartureName,
    t.ArrivalCountry,
    arr.CountryName                        AS ArrivalName,
    t.TravelDate,
    t.ModeOfTravel,
    bp.BorderPostName,
    bp.BorderType,
    CONCAT(o.OfficerFirstName, ' ', o.OfficerLastName) AS ProcessingOfficer
FROM TRAVEL_RECORD t
JOIN CITIZEN             c   ON t.NationalIDNo  = c.NationalIDNo
JOIN COUNTRY             dep ON t.DepartureCountry = dep.CountryCode
JOIN COUNTRY             arr ON t.ArrivalCountry   = arr.CountryCode
JOIN BORDER_POST         bp  ON t.BorderPostID  = bp.BorderPostID
JOIN IMMIGRATION_OFFICER o   ON t.OfficerID     = o.OfficerID;


-- V4: Visa status overview
-- Full visa details joined to citizen and officer for reporting.
CREATE OR REPLACE VIEW vw_VisaOverview AS
SELECT
    v.VisaID,
    v.NationalIDNo,
    CONCAT(c.FirstName, ' ', c.LastName)           AS CitizenName,
    c.Nationality,
    v.PassportNo,
    v.VisaType,
    v.VisaStatus,
    v.IssueDate,
    v.ExpiryDate,
    v.DurationOfStay,
    v.NumberOfEntries,
    CONCAT(o.OfficerFirstName, ' ', o.OfficerLastName) AS IssuingOfficer,
    CASE
        WHEN v.VisaStatus = 'Approved' AND v.ExpiryDate >= CURRENT_DATE
             THEN 'Valid'
        WHEN v.VisaStatus = 'Approved' AND v.ExpiryDate < CURRENT_DATE
             THEN 'Expired'
        ELSE v.VisaStatus
    END AS EffectiveStatus
FROM VISA v
JOIN CITIZEN             c ON v.NationalIDNo = c.NationalIDNo
JOIN IMMIGRATION_OFFICER o ON v.OfficerID    = o.OfficerID;


-- V5: Border post activity summary
-- Management view — crossings per post, officer count, recent activity.
CREATE OR REPLACE VIEW vw_BorderPostActivity AS
SELECT
    bp.BorderPostID,
    bp.BorderPostName,
    bp.BorderType,
    co.CountryName                         AS Country,
    COUNT(DISTINCT o.OfficerID)            AS OfficerCount,
    COUNT(DISTINCT t.TravelID)             AS TotalCrossings,
    MAX(t.TravelDate)                      AS LastCrossingDate,
    COUNT(DISTINCT apt.AppointmentID)      AS TotalAppointments
FROM BORDER_POST bp
JOIN COUNTRY             co  ON bp.CountryCode  = co.CountryCode
LEFT JOIN IMMIGRATION_OFFICER o   ON bp.BorderPostID = o.BorderPostID
LEFT JOIN TRAVEL_RECORD       t   ON bp.BorderPostID = t.BorderPostID
LEFT JOIN APPOINTMENT         apt ON bp.BorderPostID = apt.BorderPostID
GROUP BY bp.BorderPostID, bp.BorderPostName, bp.BorderType, co.CountryName;


-- ============================================================
-- STORED PROCEDURES
-- ============================================================

-- SP1: Approve a passport application
-- Validates the application exists and is pending, then creates
-- the passport record automatically and updates application status.
DELIMITER //
CREATE PROCEDURE sp_ApprovePassportApplication(
    IN  p_ApplicationID  VARCHAR(7),
    IN  p_OfficerID      VARCHAR(7),
    IN  p_PassportNo     VARCHAR(10),
    IN  p_PassportType   ENUM('Ordinary','Official'),
    IN  p_Nationality    VARCHAR(35),
    IN  p_IssuingOffice  VARCHAR(35),
    IN  p_IssueDate      DATE,
    IN  p_ExpiryDate     DATE,
    OUT p_Result         VARCHAR(100)
)
BEGIN
    DECLARE v_Status        VARCHAR(20);
    DECLARE v_AppType       VARCHAR(20);
    DECLARE v_NationalIDNo  VARCHAR(8);
    DECLARE v_ExistingActive INT;

    -- Check application exists and is pending
    SELECT ApplicationStatus, ApplicationType, NationalIDNo
    INTO   v_Status, v_AppType, v_NationalIDNo
    FROM   APPLICATION
    WHERE  ApplicationID = p_ApplicationID;

    IF v_Status IS NULL THEN
        SET p_Result = 'ERROR: Application not found';
    ELSEIF v_Status <> 'Pending' THEN
        SET p_Result = CONCAT('ERROR: Application is already ', v_Status);
    ELSEIF v_AppType = 'Visa' THEN
        SET p_Result = 'ERROR: Use sp_ApproveVisa for visa applications';
    ELSE
        -- Check citizen doesn't already have an active passport
        SELECT COUNT(*) INTO v_ExistingActive
        FROM   PASSPORT
        WHERE  NationalIDNo   = v_NationalIDNo
          AND  PassportStatus = 'Active';

        IF v_ExistingActive > 0 AND v_AppType = 'New Passport' THEN
            SET p_Result = 'ERROR: Citizen already holds an active passport';
        ELSE
            -- Archive existing active passport if renewal
            IF v_AppType = 'Renewal' THEN
                UPDATE PASSPORT
                SET    PassportStatus = 'Expired'
                WHERE  NationalIDNo   = v_NationalIDNo
                  AND  PassportStatus = 'Active';
            END IF;

            -- Create passport record
            INSERT INTO PASSPORT
                (PassportNo, NationalIDNo, ApplicationID, PassportType,
                 IssueDate, ExpiryDate, Nationality, IssuingOffice, PassportStatus)
            VALUES
                (p_PassportNo, v_NationalIDNo, p_ApplicationID, p_PassportType,
                 p_IssueDate, p_ExpiryDate, p_Nationality, p_IssuingOffice, 'Active');

            -- Update application status
            UPDATE APPLICATION
            SET    ApplicationStatus = 'Approved'
            WHERE  ApplicationID     = p_ApplicationID;

            -- Log the action
            INSERT INTO AUDIT_LOG (OfficerID, ActionType, TableAffected, RecordID)
            VALUES (p_OfficerID, 'Created', 'PASSPORT', p_PassportNo);

            SET p_Result = CONCAT('SUCCESS: Passport ', p_PassportNo, ' issued');
        END IF;
    END IF;
END //
DELIMITER ;


-- SP2: Reject an application
-- Marks the application rejected and records the reason.
DELIMITER //
CREATE PROCEDURE sp_RejectApplication(
    IN  p_ApplicationID   VARCHAR(7),
    IN  p_OfficerID       VARCHAR(7),
    IN  p_RejectionReason VARCHAR(255),
    OUT p_Result          VARCHAR(100)
)
BEGIN
    DECLARE v_Status VARCHAR(20);

    SELECT ApplicationStatus INTO v_Status
    FROM   APPLICATION
    WHERE  ApplicationID = p_ApplicationID;

    IF v_Status IS NULL THEN
        SET p_Result = 'ERROR: Application not found';
    ELSEIF v_Status <> 'Pending' THEN
        SET p_Result = CONCAT('ERROR: Application is already ', v_Status);
    ELSEIF p_RejectionReason IS NULL OR TRIM(p_RejectionReason) = '' THEN
        SET p_Result = 'ERROR: A rejection reason is required';
    ELSE
        UPDATE APPLICATION
        SET    ApplicationStatus = 'Rejected',
               RejectionReason  = p_RejectionReason
        WHERE  ApplicationID    = p_ApplicationID;

        INSERT INTO AUDIT_LOG (OfficerID, ActionType, TableAffected, RecordID)
        VALUES (p_OfficerID, 'Updated', 'APPLICATION', p_ApplicationID);

        SET p_Result = 'SUCCESS: Application rejected';
    END IF;
END //
DELIMITER ;


-- SP3: Get full citizen profile
-- Returns citizen info, all passports, active visa, and trip count
-- in one call — used by the officer detail panel.
DELIMITER //
CREATE PROCEDURE sp_GetCitizenProfile(
    IN p_NationalIDNo VARCHAR(8)
)
BEGIN
    -- Citizen details
    SELECT
        c.NationalIDNo,
        CONCAT(c.FirstName, ' ', c.LastName) AS FullName,
        c.DOB,
        TIMESTAMPDIFF(YEAR, c.DOB, CURRENT_DATE) AS Age,
        c.Gender,
        c.Nationality,
        c.CountryOfBirth,
        c.Address,
        c.Phone,
        c.Email
    FROM CITIZEN c
    WHERE c.NationalIDNo = p_NationalIDNo;

    -- All passports
    SELECT
        PassportNo,
        PassportType,
        IssueDate,
        ExpiryDate,
        PassportStatus,
        IssuingOffice
    FROM PASSPORT
    WHERE NationalIDNo = p_NationalIDNo
    ORDER BY IssueDate DESC;

    -- Active visas
    SELECT
        VisaID,
        VisaType,
        IssueDate,
        ExpiryDate,
        VisaStatus,
        DurationOfStay,
        NumberOfEntries
    FROM VISA
    WHERE NationalIDNo = p_NationalIDNo
      AND VisaStatus   = 'Approved'
      AND ExpiryDate  >= CURRENT_DATE;

    -- Travel summary
    SELECT
        COUNT(*)                                                    AS TotalTrips,
        COUNT(CASE WHEN EntryOrExit = 'entry' THEN 1 END)          AS TotalEntries,
        COUNT(CASE WHEN EntryOrExit = 'exit'  THEN 1 END)          AS TotalExits,
        MAX(TravelDate)                                             AS LastTravel
    FROM TRAVEL_RECORD
    WHERE NationalIDNo = p_NationalIDNo;
END //
DELIMITER ;


-- ============================================================
-- USER-DEFINED FUNCTIONS
-- ============================================================

-- UDF1: fn_PassportStatus
-- Returns a human-readable passport status for a citizen,
-- checking for active, expired, or no passport on record.
DELIMITER //
CREATE FUNCTION fn_PassportStatus(p_NationalIDNo VARCHAR(8))
RETURNS VARCHAR(50)
DETERMINISTIC
READS SQL DATA
BEGIN
    DECLARE v_Status    VARCHAR(20);
    DECLARE v_Expiry    DATE;
    DECLARE v_Result    VARCHAR(50);

    SELECT PassportStatus, ExpiryDate
    INTO   v_Status, v_Expiry
    FROM   PASSPORT
    WHERE  NationalIDNo   = p_NationalIDNo
      AND  PassportStatus = 'Active'
    LIMIT 1;

    IF v_Status IS NULL THEN
        SET v_Result = 'No Active Passport';
    ELSEIF v_Expiry < CURRENT_DATE THEN
        SET v_Result = 'Expired';
    ELSEIF DATEDIFF(v_Expiry, CURRENT_DATE) <= 90 THEN
        SET v_Result = CONCAT('Expiring Soon — ', DATEDIFF(v_Expiry, CURRENT_DATE), ' days');
    ELSE
        SET v_Result = CONCAT('Valid — expires ', v_Expiry);
    END IF;

    RETURN v_Result;
END //
DELIMITER ;

-- Usage example:
-- SELECT NationalIDNo, fn_PassportStatus(NationalIDNo) AS PassportStatus FROM CITIZEN;


-- UDF2: fn_TotalRevenue
-- Returns total confirmed payment revenue for a given date range.
-- Useful for monthly or quarterly financial reporting.
DELIMITER //
CREATE FUNCTION fn_TotalRevenue(
    p_DateFrom DATE,
    p_DateTo   DATE
)
RETURNS DECIMAL(12,2)
DETERMINISTIC
READS SQL DATA
BEGIN
    DECLARE v_Total DECIMAL(12,2);

    SELECT COALESCE(SUM(Amount), 0.00)
    INTO   v_Total
    FROM   PAYMENT
    WHERE  PaymentStatus = 'Confirmed'
      AND  PaymentDate  BETWEEN p_DateFrom AND p_DateTo;

    RETURN v_Total;
END //
DELIMITER ;

-- Usage example:
-- SELECT fn_TotalRevenue('2026-01-01', '2026-06-30') AS H1_Revenue;


-- ============================================================
-- END
-- ============================================================
