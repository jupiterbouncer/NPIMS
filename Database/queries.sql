-- ============================================================
-- ADVANCED QUERIES
-- ============================================================

USE NPIMS;

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


-- Q2: Passport expiry alert - passports expiring within 90 days
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


-- Q7: Revenue report - total payments by application type and month
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