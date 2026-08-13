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