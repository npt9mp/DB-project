ALTER TABLE customer
    MODIFY customerID INT NOT NULL AUTO_INCREMENT;

ALTER TABLE customer
    ADD COLUMN IF NOT EXISTS password VARCHAR(50) NULL;

UPDATE customer
SET password = CONCAT('Luffy', customerID + 100)
WHERE password IS NULL OR password = '';

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

ALTER TABLE technician
    MODIFY technicianID INT NOT NULL AUTO_INCREMENT;

ALTER TABLE technician
    ADD COLUMN IF NOT EXISTS password VARCHAR(50) NULL;

UPDATE technician
SET password = CONCAT('Zoro', technicianID + 200)
WHERE password IS NULL OR password = '';

ALTER TABLE supplier
    MODIFY supplierID INT NOT NULL AUTO_INCREMENT;

ALTER TABLE supply_order
    MODIFY orderID INT NOT NULL AUTO_INCREMENT;

ALTER TABLE supply_order
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'pending';

CREATE TABLE IF NOT EXISTS includes (
    orderID INT NOT NULL,
    product_name VARCHAR(30) NOT NULL,
    quantity INT NOT NULL DEFAULT 0,
    PRIMARY KEY (orderID, product_name),
    FOREIGN KEY (orderID) REFERENCES supply_order(orderID),
    FOREIGN KEY (product_name) REFERENCES product(product_name)
);

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
    IN p_password VARCHAR(50),
    OUT p_customer_id INT
)
BEGIN
    INSERT INTO customer (customer_name, phone_number, password)
    VALUES (p_customer_name, p_phone_number, p_password);

    SET p_customer_id = LAST_INSERT_ID();
END//

CREATE PROCEDURE customer_book_appointment(
    IN p_appointment_date DATETIME,
    IN p_total_cost DECIMAL(10,2),
    OUT p_appointment_id INT
)
BEGIN
    DECLARE v_purchase_id INT;

    IF TIME(p_appointment_date) < '09:00:00'
       OR TIME(p_appointment_date) >= '17:00:00'
       OR MOD(MINUTE(p_appointment_date), 5) <> 0
       OR SECOND(p_appointment_date) <> 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Customer appointments must be between 9:00 AM and 5:00 PM in 5-minute increments.';
    END IF;

    IF p_total_cost IS NULL OR p_total_cost <= 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Appointment cost must be greater than zero.';
    END IF;

    INSERT INTO purchase (customerID, cost, purchase_date)
    VALUES (@app_customer_id, p_total_cost, p_appointment_date);

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
END//

CREATE PROCEDURE customer_view_appointments()
BEGIN
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
BEGIN
    SELECT purchaseID, customerID, cost, purchase_date
    FROM purchase
    WHERE customerID = @app_customer_id
    ORDER BY purchase_date DESC, purchaseID DESC;
END//

CREATE PROCEDURE customer_view_services()
BEGIN
    SELECT service_name, service_cost
    FROM service
    ORDER BY service_name;
END//

DELIMITER ;
