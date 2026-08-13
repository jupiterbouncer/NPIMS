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

