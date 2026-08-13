-- ============================================================
-- TRIGGERS
-- ============================================================

DELIMITER //

-- CITIZEN: DOB cannot be in the future (INSERT)
CREATE TRIGGER trg_citizen_dob_insert
BEFORE INSERT ON CITIZEN
FOR EACH ROW
BEGIN
    IF NEW.DOB > CURRENT_DATE THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Date of birth cannot be in the future';
    END IF;
END //

-- CITIZEN: DOB cannot be in the future (UPDATE)
CREATE TRIGGER trg_citizen_dob_update
BEFORE UPDATE ON CITIZEN
FOR EACH ROW
BEGIN
    IF NEW.DOB > CURRENT_DATE THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Date of birth cannot be in the future';
    END IF;
END //

-- TRAVEL_RECORD: travel date cannot be in the future (INSERT)
CREATE TRIGGER trg_travel_date_insert
BEFORE INSERT ON TRAVEL_RECORD
FOR EACH ROW
BEGIN
    IF NEW.TravelDate > CURRENT_DATE THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Travel date cannot be in the future';
    END IF;
END //

-- TRAVEL_RECORD: travel date cannot be in the future (UPDATE)
CREATE TRIGGER trg_travel_date_update
BEFORE UPDATE ON TRAVEL_RECORD
FOR EACH ROW
BEGIN
    IF NEW.TravelDate > CURRENT_DATE THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Travel date cannot be in the future';
    END IF;
END //

CREATE TRIGGER trg_appointment_date_insert
BEFORE INSERT ON APPOINTMENT
FOR EACH ROW
BEGIN
    IF NEW.AppointmentStatus = 'Scheduled' AND NEW.AppointmentDate < CURRENT_DATE THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Scheduled appointments cannot be in the past';
    END IF;
END //

CREATE TRIGGER trg_appointment_date_update
BEFORE UPDATE ON APPOINTMENT
FOR EACH ROW
BEGIN
    IF NEW.AppointmentStatus = 'Scheduled' AND NEW.AppointmentDate < CURRENT_DATE THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Scheduled appointments cannot be in the past';
    END IF;
END //

CREATE TRIGGER trg_visa_rejected_passport_insert
BEFORE INSERT ON VISA
FOR EACH ROW
BEGIN
    IF NEW.VisaStatus = 'Rejected' AND NEW.PassportNo IS NOT NULL THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'A rejected visa must not be linked to a passport';
    END IF;
END //

CREATE TRIGGER trg_visa_rejected_passport_update
BEFORE UPDATE ON VISA
FOR EACH ROW
BEGIN
    IF NEW.VisaStatus = 'Rejected' AND NEW.PassportNo IS NOT NULL THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'A rejected visa must not be linked to a passport';
    END IF;
END //

CREATE TRIGGER trg_visa_dates_insert
BEFORE INSERT ON VISA
FOR EACH ROW
BEGIN
    IF NEW.IssueDate IS NOT NULL AND NEW.ExpiryDate IS NOT NULL 
       AND NEW.ExpiryDate <= NEW.IssueDate THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Visa expiry date must be after issue date';
    END IF;
END //

CREATE TRIGGER trg_visa_dates_update
BEFORE UPDATE ON VISA
FOR EACH ROW
BEGIN
    IF NEW.IssueDate IS NOT NULL AND NEW.ExpiryDate IS NOT NULL 
       AND NEW.ExpiryDate <= NEW.IssueDate THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Visa expiry date must be after issue date';
    END IF;
END //

CREATE TRIGGER trg_travel_countries_insert
BEFORE INSERT ON TRAVEL_RECORD
FOR EACH ROW
BEGIN
    IF NEW.DepartureCountry = NEW.ArrivalCountry THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Departure and arrival countries cannot be the same';
    END IF;
END //

CREATE TRIGGER trg_travel_countries_update
BEFORE UPDATE ON TRAVEL_RECORD
FOR EACH ROW
BEGIN
    IF NEW.DepartureCountry = NEW.ArrivalCountry THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Departure and arrival countries cannot be the same';
    END IF;
END //
DELIMITER ;

-- ============================================================
-- TRIGGERS FOR AUDIT LOGGING
-- ============================================================
DELIMITER //

-- Log every new passport creation
CREATE TRIGGER trg_audit_passport_insert
AFTER INSERT ON PASSPORT
FOR EACH ROW
BEGIN
    INSERT INTO AUDIT_LOG (OfficerID, ActionType, TableAffected, RecordID)
    SELECT a.OfficerID, 'Created', 'PASSPORT', NEW.PassportNo
    FROM APPLICATION a
    WHERE a.ApplicationID = NEW.ApplicationID;
END //

-- Log every passport status change
CREATE TRIGGER trg_audit_passport_update
AFTER UPDATE ON PASSPORT
FOR EACH ROW
BEGIN
    INSERT INTO AUDIT_LOG (OfficerID, ActionType, TableAffected, RecordID)
    SELECT a.OfficerID, 'Updated', 'PASSPORT', NEW.PassportNo
    FROM APPLICATION a
    WHERE a.ApplicationID = NEW.ApplicationID;
END //

-- Log every visa decision
CREATE TRIGGER trg_audit_visa_update
AFTER UPDATE ON VISA
FOR EACH ROW
BEGIN
    INSERT INTO AUDIT_LOG (OfficerID, ActionType, TableAffected, RecordID)
    VALUES (NEW.OfficerID, 'Updated', 'VISA', NEW.VisaID);
END //

-- Log every new travel record
CREATE TRIGGER trg_audit_travel_insert
AFTER INSERT ON TRAVEL_RECORD
FOR EACH ROW
BEGIN
    INSERT INTO AUDIT_LOG (OfficerID, ActionType, TableAffected, RecordID)
    VALUES (NEW.OfficerID, 'Created', 'TRAVEL_RECORD', NEW.TravelID);
END //

-- Log every new citizen registration
CREATE TRIGGER trg_audit_citizen_insert
AFTER INSERT ON CITIZEN
FOR EACH ROW
BEGIN
    INSERT INTO AUDIT_LOG (OfficerID, ActionType, TableAffected, RecordID)
    VALUES ('OF00001', 'Created', 'CITIZEN', NEW.NationalIDNo);
END //

DELIMITER ;