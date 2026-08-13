-- ============================================================
-- 1. COUNTRY
-- ============================================================
CREATE TABLE COUNTRY (
    CountryCode  CHAR(3)      NOT NULL,
    CountryName  VARCHAR(35)  NOT NULL,
    Continent    ENUM(
                     'Africa','Europe','Asia',
                     'North America','South America',
                     'Australia','Antarctica'
                 ) NOT NULL,
    VisaRequired ENUM('Yes','No') NOT NULL DEFAULT 'Yes',
    IsActive     TINYINT(1)   NOT NULL DEFAULT 1,

    CONSTRAINT pk_country PRIMARY KEY (CountryCode),
    CONSTRAINT uq_country_name UNIQUE (CountryName),
    CONSTRAINT chk_country_code CHECK (CountryCode = UPPER(CountryCode))
) ENGINE=InnoDB;


-- ============================================================
-- 2. CITIZEN
-- ============================================================
CREATE TABLE CITIZEN (
    NationalIDNo  VARCHAR(8)   NOT NULL,
    FirstName     VARCHAR(35)  NOT NULL,
    LastName      VARCHAR(35)  NOT NULL,
    OtherName     VARCHAR(35)  NULL,
    DOB           DATE         NOT NULL,
    CountryOfBirth CHAR(3)     NOT NULL,
    Gender        ENUM('Male','Female') NOT NULL,
    Nationality   VARCHAR(35)  NOT NULL,
    Address       VARCHAR(50)  NOT NULL,
    Phone         VARCHAR(20)  NOT NULL,
    Email         VARCHAR(50)  NOT NULL,

    CONSTRAINT pk_citizen       PRIMARY KEY (NationalIDNo),
    CONSTRAINT uq_citizen_email UNIQUE (Email),

    CONSTRAINT fk_citizen_country
        FOREIGN KEY (CountryOfBirth)
        REFERENCES COUNTRY(CountryCode)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE INDEX idx_citizen_name  ON CITIZEN(LastName, FirstName);
CREATE INDEX idx_citizen_phone ON CITIZEN(Phone);


-- ============================================================
-- 3. BORDER_POST
-- ============================================================
CREATE TABLE BORDER_POST (
    BorderPostID   VARCHAR(7)  NOT NULL,
    BorderPostName VARCHAR(35) NOT NULL,
    CountryCode    CHAR(3)     NOT NULL,
    BorderType     ENUM('Airport','Land','Sea') NOT NULL,

    CONSTRAINT pk_borderpost PRIMARY KEY (BorderPostID),

    CONSTRAINT uq_borderpost_name_country
        UNIQUE (BorderPostName, CountryCode),

    CONSTRAINT fk_borderpost_country
        FOREIGN KEY (CountryCode)
        REFERENCES COUNTRY(CountryCode)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE INDEX idx_borderpost_country ON BORDER_POST(CountryCode);


-- ============================================================
-- 4. IMMIGRATION_OFFICER
-- ============================================================
CREATE TABLE IMMIGRATION_OFFICER (
    OfficerID        VARCHAR(7)  NOT NULL,
    OfficerFirstName VARCHAR(35) NOT NULL,
    OfficerLastName  VARCHAR(35) NOT NULL,
    BorderPostID     VARCHAR(7)  NOT NULL,

    CONSTRAINT pk_officer PRIMARY KEY (OfficerID),

    CONSTRAINT fk_officer_borderpost
        FOREIGN KEY (BorderPostID)
        REFERENCES BORDER_POST(BorderPostID)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE INDEX idx_officer_borderpost ON IMMIGRATION_OFFICER(BorderPostID);
CREATE INDEX idx_officer_name       ON IMMIGRATION_OFFICER(OfficerLastName, OfficerFirstName);


-- ============================================================
-- 5. APPLICATION
-- ============================================================
CREATE TABLE APPLICATION (
    ApplicationID     VARCHAR(7)  NOT NULL,
    NationalIDNo      VARCHAR(8)  NOT NULL,
    OfficerID         VARCHAR(7)  NOT NULL,
    ApplicationType   ENUM('New Passport','Renewal','Visa') NOT NULL,
    ApplicationStatus ENUM(
                          'Pending','Processing',
                          'Approved','Rejected','Withdrawn'
                      ) NOT NULL DEFAULT 'Pending',
    ApplicationDate   DATE        NOT NULL,
    RejectionReason   VARCHAR(255) NULL,

    CONSTRAINT pk_application PRIMARY KEY (ApplicationID),

    CONSTRAINT fk_application_citizen
        FOREIGN KEY (NationalIDNo)
        REFERENCES CITIZEN(NationalIDNo)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_application_officer
        FOREIGN KEY (OfficerID)
        REFERENCES IMMIGRATION_OFFICER(OfficerID)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE INDEX idx_application_citizen      ON APPLICATION(NationalIDNo);
CREATE INDEX idx_application_officer      ON APPLICATION(OfficerID);
CREATE INDEX idx_application_status_type  ON APPLICATION(ApplicationStatus, ApplicationType);
CREATE INDEX idx_application_date         ON APPLICATION(ApplicationDate);


-- ============================================================
-- 6. PAYMENT
-- ============================================================
CREATE TABLE PAYMENT (
    PaymentRefNo  VARCHAR(7)   NOT NULL,
    ApplicationID VARCHAR(7)   NOT NULL,
    NationalIDNo  VARCHAR(8)   NOT NULL,
    Amount        DECIMAL(10,2) NOT NULL,
    PaymentDate   DATE         NOT NULL,
    PaymentMethod ENUM('E-Transfer','Cash Deposit') NOT NULL,
    PaymentFor    ENUM('Passport Application','Renewal','Appeal') NOT NULL,
    PaymentStatus ENUM('Confirmed','Void') NOT NULL DEFAULT 'Confirmed',

    CONSTRAINT pk_payment         PRIMARY KEY (PaymentRefNo),
    CONSTRAINT uq_payment_app     UNIQUE (ApplicationID),

    CONSTRAINT fk_payment_application
        FOREIGN KEY (ApplicationID)
        REFERENCES APPLICATION(ApplicationID)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_payment_citizen
        FOREIGN KEY (NationalIDNo)
        REFERENCES CITIZEN(NationalIDNo)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT chk_payment_amount CHECK (Amount > 0)
) ENGINE=InnoDB;

CREATE INDEX idx_payment_citizen ON PAYMENT(NationalIDNo);
CREATE INDEX idx_payment_date    ON PAYMENT(PaymentDate);


-- ============================================================
-- 7. APPOINTMENT
-- ============================================================
CREATE TABLE APPOINTMENT (
    AppointmentID     VARCHAR(7)  NOT NULL,
    ApplicationID     VARCHAR(7)  NOT NULL,
    NationalIDNo      VARCHAR(8)  NOT NULL,
    BorderPostID      VARCHAR(7)  NOT NULL,
    AppointmentDate   DATE        NOT NULL,
    AppointmentStatus ENUM(
                          'Scheduled','Completed',
                          'Canceled','No Show'
                      ) NOT NULL DEFAULT 'Scheduled',

    CONSTRAINT pk_appointment     PRIMARY KEY (AppointmentID),
    CONSTRAINT uq_appointment_app UNIQUE (ApplicationID),

    CONSTRAINT fk_appointment_application
        FOREIGN KEY (ApplicationID)
        REFERENCES APPLICATION(ApplicationID)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_appointment_citizen
        FOREIGN KEY (NationalIDNo)
        REFERENCES CITIZEN(NationalIDNo)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_appointment_borderpost
        FOREIGN KEY (BorderPostID)
        REFERENCES BORDER_POST(BorderPostID)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE INDEX idx_appointment_borderpost_date ON APPOINTMENT(BorderPostID, AppointmentDate);
CREATE INDEX idx_appointment_status          ON APPOINTMENT(AppointmentStatus);


-- ============================================================
-- 8. PASSPORT
-- ============================================================
CREATE TABLE PASSPORT (
    PassportNo     VARCHAR(10)  NOT NULL,
    NationalIDNo   VARCHAR(8)   NOT NULL,
    ApplicationID  VARCHAR(7)   NOT NULL,
    PassportType   ENUM('Ordinary','Official') NOT NULL,
    IssueDate      DATE         NOT NULL,
    ExpiryDate     DATE         NOT NULL,
    Nationality    VARCHAR(35)  NOT NULL,
    IssuingOffice  VARCHAR(35)  NOT NULL,
    PassportStatus ENUM('Active','Expired','Revoked') NOT NULL DEFAULT 'Active',

    CONSTRAINT pk_passport         PRIMARY KEY (PassportNo),
    CONSTRAINT uq_passport_app     UNIQUE (ApplicationID),

    CONSTRAINT fk_passport_citizen
        FOREIGN KEY (NationalIDNo)
        REFERENCES CITIZEN(NationalIDNo)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_passport_application
        FOREIGN KEY (ApplicationID)
        REFERENCES APPLICATION(ApplicationID)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT chk_passport_dates
        CHECK (ExpiryDate > IssueDate)
) ENGINE=InnoDB;

CREATE INDEX idx_passport_citizen       ON PASSPORT(NationalIDNo);
CREATE INDEX idx_passport_status_expiry ON PASSPORT(PassportStatus, ExpiryDate);


-- ============================================================
-- 9. VISA
-- ============================================================
CREATE TABLE VISA (
    VisaID          VARCHAR(12)  NOT NULL,
    NationalIDNo    VARCHAR(8)   NOT NULL,
    PassportNo      VARCHAR(10)  NULL,
    ApplicationID   VARCHAR(7)   NOT NULL,
    OfficerID       VARCHAR(7)   NOT NULL,
    VisaType        VARCHAR(35)  NOT NULL,
    IssueDate       DATE         NULL,
    ExpiryDate      DATE         NULL,
    VisaStatus      ENUM('Pending','Approved','Rejected','Expired')
                                 NOT NULL DEFAULT 'Pending',
    DurationOfStay  INT          NULL,
    NumberOfEntries ENUM('Single','Multiple') NULL,

    CONSTRAINT pk_visa         PRIMARY KEY (VisaID),
    CONSTRAINT uq_visa_app     UNIQUE (ApplicationID),

    CONSTRAINT fk_visa_citizen
        FOREIGN KEY (NationalIDNo)
        REFERENCES CITIZEN(NationalIDNo)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_visa_passport
        FOREIGN KEY (PassportNo)
        REFERENCES PASSPORT(PassportNo)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_visa_application
        FOREIGN KEY (ApplicationID)
        REFERENCES APPLICATION(ApplicationID)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_visa_officer
        FOREIGN KEY (OfficerID)
        REFERENCES IMMIGRATION_OFFICER(OfficerID)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT chk_visa_dates
        CHECK (
            (IssueDate IS NULL AND ExpiryDate IS NULL)
            OR (IssueDate IS NOT NULL AND ExpiryDate > IssueDate)
        ),

    CONSTRAINT chk_visa_duration
        CHECK (DurationOfStay IS NULL OR DurationOfStay > 0)
) ENGINE=InnoDB;

CREATE INDEX idx_visa_passport      ON VISA(PassportNo);
CREATE INDEX idx_visa_citizen       ON VISA(NationalIDNo);
CREATE INDEX idx_visa_officer       ON VISA(OfficerID);
CREATE INDEX idx_visa_status_expiry ON VISA(VisaStatus, ExpiryDate);


-- ============================================================
-- 10. TRAVEL_RECORD
-- ============================================================
CREATE TABLE TRAVEL_RECORD (
    TravelID         VARCHAR(7)  NOT NULL,
    NationalIDNo     VARCHAR(8)  NOT NULL,
    PassportNo       VARCHAR(10) NOT NULL,
    OfficerID        VARCHAR(7)  NOT NULL,
    BorderPostID     VARCHAR(7)  NOT NULL,
    DepartureCountry CHAR(3)     NOT NULL,
    ArrivalCountry   CHAR(3)     NOT NULL,
    TravelDate       DATE        NOT NULL,
    EntryOrExit      ENUM('entry','exit') NOT NULL,   
    ModeOfTravel     ENUM('Air','Sea','Land') NOT NULL,

    CONSTRAINT pk_travel PRIMARY KEY (TravelID),

    CONSTRAINT fk_travel_citizen
        FOREIGN KEY (NationalIDNo)
        REFERENCES CITIZEN(NationalIDNo)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_travel_passport
        FOREIGN KEY (PassportNo)
        REFERENCES PASSPORT(PassportNo)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_travel_officer
        FOREIGN KEY (OfficerID)
        REFERENCES IMMIGRATION_OFFICER(OfficerID)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_travel_borderpost
        FOREIGN KEY (BorderPostID)
        REFERENCES BORDER_POST(BorderPostID)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_travel_departure
        FOREIGN KEY (DepartureCountry)
        REFERENCES COUNTRY(CountryCode)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_travel_arrival
        FOREIGN KEY (ArrivalCountry)
        REFERENCES COUNTRY(CountryCode)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE INDEX idx_travel_citizen_date   ON TRAVEL_RECORD(NationalIDNo, TravelDate);
CREATE INDEX idx_travel_passport       ON TRAVEL_RECORD(PassportNo);
CREATE INDEX idx_travel_borderpost     ON TRAVEL_RECORD(BorderPostID, TravelDate);
CREATE INDEX idx_travel_route          ON TRAVEL_RECORD(DepartureCountry, ArrivalCountry);


-- ============================================================
-- 11. AUDIT_LOG
-- ============================================================
CREATE TABLE AUDIT_LOG (
    LogID           BIGINT UNSIGNED AUTO_INCREMENT NOT NULL,
    OfficerID       VARCHAR(7)   NOT NULL,
    ActionType      ENUM('Viewed','Created','Updated','Deleted') NOT NULL,
    TableAffected   VARCHAR(35)  NOT NULL,
    RecordID        VARCHAR(20)  NOT NULL,
    ActionTimestamp DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_audit PRIMARY KEY (LogID),

    CONSTRAINT fk_audit_officer
        FOREIGN KEY (OfficerID)
        REFERENCES IMMIGRATION_OFFICER(OfficerID)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE INDEX idx_audit_officer_time  ON AUDIT_LOG(OfficerID, ActionTimestamp);
CREATE INDEX idx_audit_table_record  ON AUDIT_LOG(TableAffected, RecordID);
CREATE INDEX idx_audit_timestamp     ON AUDIT_LOG(ActionTimestamp);