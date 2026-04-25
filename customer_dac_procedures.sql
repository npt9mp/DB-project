CREATE USER IF NOT EXISTS 'npt9mp_customer_app'@'%'
IDENTIFIED BY 'customer_app_password';

REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'npt9mp_customer_app'@'%';

ALTER TABLE customer
    MODIFY customerID INT NOT NULL AUTO_INCREMENT;

ALTER TABLE purchase
    MODIFY purchaseID INT NOT NULL AUTO_INCREMENT;

ALTER TABLE appointment
    MODIFY appointmentID INT NOT NULL AUTO_INCREMENT;

ALTER TABLE appointment
    MODIFY purchaseID INT NULL;

ALTER TABLE technician
    MODIFY technicianID INT NOT NULL AUTO_INCREMENT;

ALTER TABLE supply_order
    MODIFY orderID INT NOT NULL AUTO_INCREMENT;

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
    IN p_appointment_date DATE,
    OUT p_appointment_id INT
)
SQL SECURITY DEFINER
BEGIN
    IF @app_customer_id IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Customer session is not set.';
    END IF;

    INSERT INTO appointment (customerID, appointment_date)
    VALUES (@app_customer_id, p_appointment_date);

    SET p_appointment_id = LAST_INSERT_ID();
END//

CREATE PROCEDURE customer_view_appointments()
SQL SECURITY DEFINER
BEGIN
    IF @app_customer_id IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Customer session is not set.';
    END IF;

    SELECT appointmentID, customerID, purchaseID, appointment_date
    FROM appointment
    WHERE customerID = @app_customer_id
    ORDER BY appointment_date DESC, appointmentID DESC;
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
