CREATE USER IF NOT EXISTS 'npt9mp_customer_app'@'%'
IDENTIFIED BY 'customer_app_password';

ALTER USER 'npt9mp_customer_app'@'%'
IDENTIFIED BY 'customer_app_password';

REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'npt9mp_customer_app'@'%';

ALTER TABLE customer
    MODIFY customerID INT NOT NULL AUTO_INCREMENT;

ALTER TABLE purchase
    MODIFY purchaseID INT NOT NULL AUTO_INCREMENT;

ALTER TABLE appointment
    MODIFY appointmentID INT NOT NULL AUTO_INCREMENT;

ALTER TABLE appointment
    MODIFY appointment_date DATETIME NOT NULL;

ALTER TABLE appointment
    MODIFY purchaseID INT NULL;

ALTER TABLE appointment
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'pending';

UPDATE appointment
SET status = 'assigned'
WHERE status = 'pending'
  AND appointmentID IN (SELECT appointmentID FROM schedules);

DROP PROCEDURE IF EXISTS migrate_preferred_services_to_orders;

DELIMITER //
CREATE PROCEDURE migrate_preferred_services_to_orders()
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'appointment'
          AND COLUMN_NAME = 'preferred_service_name'
    ) THEN
        SET @migration_sql = '
            INSERT INTO orders (service_name, appointmentID)
            SELECT a.preferred_service_name, a.appointmentID
            FROM appointment a
            JOIN service s ON s.service_name = a.preferred_service_name
            WHERE a.preferred_service_name IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM orders o WHERE o.appointmentID = a.appointmentID
              )';
        PREPARE migration_stmt FROM @migration_sql;
        EXECUTE migration_stmt;
        DEALLOCATE PREPARE migration_stmt;
    END IF;
END//
DELIMITER ;

CALL migrate_preferred_services_to_orders();
DROP PROCEDURE IF EXISTS migrate_preferred_services_to_orders;

ALTER TABLE appointment
    DROP COLUMN IF EXISTS preferredTechnicianID;

ALTER TABLE appointment
    DROP COLUMN IF EXISTS preferred_service_name;

ALTER TABLE technician
    MODIFY technicianID INT NOT NULL AUTO_INCREMENT;

ALTER TABLE supply_order
    MODIFY orderID INT NOT NULL AUTO_INCREMENT;

UPDATE appointment
SET appointment_date = TIMESTAMP(DATE(appointment_date), '09:00:00')
WHERE TIME(appointment_date) = '00:00:00';

DROP PROCEDURE IF EXISTS customer_book_appointment;
DROP PROCEDURE IF EXISTS customer_register;
DROP PROCEDURE IF EXISTS customer_view_appointments;
DROP PROCEDURE IF EXISTS customer_view_purchases;
DROP PROCEDURE IF EXISTS customer_view_services;

DELIMITER //

CREATE PROCEDURE customer_register(
    IN p_customer_name VARCHAR(255),
    IN p_phone_number VARCHAR(50),
    OUT p_customer_id INT
)
SQL SECURITY DEFINER
BEGIN
    INSERT INTO customer (customer_name, phone_number)
    VALUES (p_customer_name, p_phone_number);

    SET p_customer_id = LAST_INSERT_ID();
END//

CREATE PROCEDURE customer_book_appointment(
    IN p_appointment_date DATETIME,
    IN p_service_names TEXT,
    OUT p_appointment_id INT
)
SQL SECURITY DEFINER
BEGIN
    DECLARE v_remaining TEXT;
    DECLARE v_service_name VARCHAR(255);
    DECLARE v_pos INT DEFAULT 0;
    DECLARE v_service_cost DECIMAL(10,2) DEFAULT 0;
    DECLARE v_total_cost DECIMAL(10,2) DEFAULT 0;
    DECLARE v_purchase_id INT;

    IF @app_customer_id IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Customer session is not set.';
    END IF;

    IF TIME(p_appointment_date) < '09:00:00'
       OR TIME(p_appointment_date) >= '17:00:00'
       OR MOD(MINUTE(p_appointment_date), 5) <> 0
       OR SECOND(p_appointment_date) <> 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Customer appointments must be between 9:00 AM and 5:00 PM in 5-minute increments.';
    END IF;

    IF p_service_names IS NULL OR p_service_names = '' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'At least one service is required.';
    END IF;

    SET v_remaining = p_service_names;
    WHILE v_remaining <> '' DO
        SET v_pos = LOCATE('|', v_remaining);
        IF v_pos = 0 THEN
            SET v_service_name = v_remaining;
            SET v_remaining = '';
        ELSE
            SET v_service_name = SUBSTRING(v_remaining, 1, v_pos - 1);
            SET v_remaining = SUBSTRING(v_remaining, v_pos + 1);
        END IF;

        SELECT COALESCE(
            (SELECT service_cost FROM service WHERE service_name = v_service_name LIMIT 1),
            -1
        )
        INTO v_service_cost;

        IF v_service_cost < 0 THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Selected service does not exist.';
        END IF;

        SET v_total_cost = v_total_cost + v_service_cost;
    END WHILE;

    INSERT INTO purchase (customerID, cost, purchase_date)
    VALUES (@app_customer_id, v_total_cost, p_appointment_date);

    SET v_purchase_id = LAST_INSERT_ID();

    INSERT INTO appointment (
        customerID,
        purchaseID,
        appointment_date,
        status
    )
    VALUES (
        @app_customer_id,
        v_purchase_id,
        p_appointment_date,
        'pending'
    );

    SET p_appointment_id = LAST_INSERT_ID();

    SET v_remaining = p_service_names;
    WHILE v_remaining <> '' DO
        SET v_pos = LOCATE('|', v_remaining);
        IF v_pos = 0 THEN
            SET v_service_name = v_remaining;
            SET v_remaining = '';
        ELSE
            SET v_service_name = SUBSTRING(v_remaining, 1, v_pos - 1);
            SET v_remaining = SUBSTRING(v_remaining, v_pos + 1);
        END IF;

        INSERT INTO orders (service_name, appointmentID)
        VALUES (v_service_name, p_appointment_id);
    END WHILE;
END//

CREATE PROCEDURE customer_view_appointments()
SQL SECURITY DEFINER
BEGIN
    IF @app_customer_id IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Customer session is not set.';
    END IF;

    SELECT a.appointmentID, a.customerID, a.purchaseID, a.appointment_date,
           GROUP_CONCAT(o.service_name ORDER BY o.service_name SEPARATOR ", ") AS services,
           a.status
    FROM appointment a
    LEFT JOIN orders o ON a.appointmentID = o.appointmentID
    WHERE a.customerID = @app_customer_id
    GROUP BY a.appointmentID, a.customerID, a.purchaseID, a.appointment_date, a.status
    ORDER BY a.appointment_date DESC, a.appointmentID DESC;
END//

CREATE PROCEDURE customer_view_purchases()
SQL SECURITY DEFINER
BEGIN
    IF @app_customer_id IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Customer session is not set.';
    END IF;

    SELECT purchaseID, customerID, cost, purchase_date
    FROM purchase
    WHERE customerID = @app_customer_id
    ORDER BY purchase_date DESC, purchaseID DESC;
END//

CREATE PROCEDURE customer_view_services()
SQL SECURITY DEFINER
BEGIN
    SELECT service_name, service_cost
    FROM service
    ORDER BY service_name;
END//

DELIMITER ;

GRANT EXECUTE ON PROCEDURE customer_book_appointment
TO 'npt9mp_customer_app'@'%';

GRANT EXECUTE ON PROCEDURE customer_register
TO 'npt9mp_customer_app'@'%';

GRANT EXECUTE ON PROCEDURE customer_view_appointments
TO 'npt9mp_customer_app'@'%';

GRANT EXECUTE ON PROCEDURE customer_view_purchases
TO 'npt9mp_customer_app'@'%';

GRANT EXECUTE ON PROCEDURE customer_view_services
TO 'npt9mp_customer_app'@'%';

FLUSH PRIVILEGES;
