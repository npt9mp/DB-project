import csv
import io
from datetime import date, datetime

from flask import (Flask, flash, redirect, render_template, request,
                   session, url_for, Response)

import config
from db import get_db, query

app = Flask(__name__)
app.secret_key = config.SECRET_KEY


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Customers can only register, book appointments, view their appointments and purchases, and view services.', 'warning')
            return redirect(url_for('appointments'))
        return f(*args, **kwargs)
    return wrapper


CUSTOMER_ALLOWED_ENDPOINTS = {
    'static',
    'index',
    'login',
    'logout',
    'register',
    'appointments',
    'appointment_add',
    'purchases',
    'services',
}


def is_customer():
    return session.get('role') == 'customer'


def current_customer_id():
    return session.get('customer_id')


def clear_result_sets(cur):
    while cur.nextset():
        pass


def call_customer_procedure(sql, args=None, fetch=True, commit=False):
    conn = get_db(customer=True, customer_id=current_customer_id())
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args or ())
            rows = cur.fetchall() if fetch else None
        if commit:
            conn.commit()
        return rows
    finally:
        conn.close()


@app.before_request
def restrict_customer_routes():
    if session.get('role') != 'customer':
        return None
    if request.endpoint in CUSTOMER_ALLOWED_ENDPOINTS:
        return None
    flash('Customers can only register, book appointments, view their appointments and purchases, and view services.', 'warning')
    return redirect(url_for('appointments'))


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route('/', methods=['GET'])
def index():
    if is_customer():
        return redirect(url_for('appointments'))
    return redirect(url_for('dashboard'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if username == config.ADMIN_USERNAME and password == config.ADMIN_PASSWORD:
            session['user'] = username
            session['role'] = 'admin'
            flash('Welcome back!', 'success')
            return redirect(url_for('dashboard'))

        customer = query(
            '''SELECT customerID, customer_name
               FROM customer
               WHERE CAST(customerID AS CHAR) = %s AND phone_number = %s''',
            (username, password),
            one=True,
        )
        if customer:
            session['user'] = customer['customer_name']
            session['role'] = 'customer'
            session['customer_id'] = customer['customerID']
            flash('Welcome back!', 'success')
            return redirect(url_for('appointments'))

        flash('Invalid username or password.', 'danger')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('customer_name', '').strip()
        phone = request.form.get('phone_number', '').strip()
        if not name or not phone:
            flash('Name and phone number are required.', 'warning')
            return render_template('customer_form.html', action='Register', customer=None)

        conn = get_db(customer=True)
        try:
            with conn.cursor() as cur:
                cur.execute('CALL customer_register(%s, %s, @new_customer_id)', (name, phone))
                clear_result_sets(cur)
                cur.execute('SELECT @new_customer_id AS customerID')
                customer_id = cur.fetchone()['customerID']
            conn.commit()
        finally:
            conn.close()

        session['user'] = name
        session['role'] = 'customer'
        session['customer_id'] = customer_id
        flash('Registration complete.', 'success')
        return redirect(url_for('appointments'))

    return render_template('customer_form.html', action='Register', customer=None)


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route('/dashboard')
@login_required
def dashboard():
    if is_customer():
        return redirect(url_for('appointments'))

    today = date.today().isoformat()

    total_customers = query('SELECT COUNT(*) AS n FROM customer', one=True)['n']
    total_services  = query('SELECT COUNT(*) AS n FROM service', one=True)['n']
    total_technicians = query('SELECT COUNT(*) AS n FROM technician', one=True)['n']

    today_appts = query(
        'SELECT COUNT(*) AS n FROM appointment WHERE appointment_date = %s',
        (today,), one=True
    )['n']

    week_revenue = query(
        '''SELECT COALESCE(SUM(cost), 0) AS total
           FROM purchase
           WHERE purchase_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)''',
        one=True
    )['total']

    low_stock = query(
        '''SELECT product_name, product_type, stock_quantity
           FROM product
           WHERE stock_quantity <= 5
           ORDER BY stock_quantity ASC, product_name'''
    )

    popular_services = query(
        '''SELECT o.service_name, COUNT(*) AS times_booked
           FROM orders o
           GROUP BY o.service_name
           ORDER BY times_booked DESC
           LIMIT 5'''
    )

    recent_appts = query(
        '''SELECT a.appointmentID, c.customer_name, a.appointment_date,
                  GROUP_CONCAT(o.service_name ORDER BY o.service_name SEPARATOR ", ") AS services,
                  p.cost
           FROM appointment a
           JOIN customer c ON a.customerID = c.customerID
           LEFT JOIN purchase p ON a.purchaseID = p.purchaseID
           LEFT JOIN orders o ON a.appointmentID = o.appointmentID
           GROUP BY a.appointmentID, c.customer_name, a.appointment_date, p.cost
           ORDER BY a.appointment_date DESC, a.appointmentID DESC
           LIMIT 10'''
    )

    return render_template('dashboard.html',
        total_customers=total_customers,
        total_services=total_services,
        total_technicians=total_technicians,
        today_appts=today_appts,
        week_revenue=week_revenue,
        low_stock=low_stock,
        popular_services=popular_services,
        recent_appts=recent_appts,
    )


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

@app.route('/customers')
@admin_required
def customers():
    search = request.args.get('search', '').strip()
    if search:
        rows = query(
            '''SELECT * FROM customer
               WHERE customer_name LIKE %s OR phone_number LIKE %s
               ORDER BY customer_name''',
            (f'%{search}%', f'%{search}%')
        )
    else:
        rows = query('SELECT * FROM customer ORDER BY customer_name')
    return render_template('customers.html', customers=rows, search=search)


@app.route('/customers/add', methods=['GET', 'POST'])
@admin_required
def customer_add():
    if request.method == 'POST':
        name  = request.form['customer_name'].strip()
        phone = request.form['phone_number'].strip()
        if not name or not phone:
            flash('Name and phone number are required.', 'warning')
            return render_template('customer_form.html', action='Add', customer=None)
        try:
            query(
                'INSERT INTO customer (customer_name, phone_number) VALUES (%s, %s)',
                (name, phone), commit=True
            )
            flash(f'Customer "{name}" added.', 'success')
            return redirect(url_for('customers'))
        except Exception as e:
            flash(f'Error: {e}', 'danger')
    return render_template('customer_form.html', action='Add', customer=None)


@app.route('/customers/<int:cid>/edit', methods=['GET', 'POST'])
@admin_required
def customer_edit(cid):
    customer = query('SELECT * FROM customer WHERE customerID = %s', (cid,), one=True)
    if not customer:
        flash('Customer not found.', 'warning')
        return redirect(url_for('customers'))
    if request.method == 'POST':
        name  = request.form['customer_name'].strip()
        phone = request.form['phone_number'].strip()
        try:
            query(
                'UPDATE customer SET customer_name=%s, phone_number=%s WHERE customerID=%s',
                (name, phone, cid), commit=True
            )
            flash(f'Customer updated.', 'success')
            return redirect(url_for('customers'))
        except Exception as e:
            flash(f'Error: {e}', 'danger')
    return render_template('customer_form.html', action='Edit', customer=customer)


@app.route('/customers/<int:cid>/delete', methods=['POST'])
@admin_required
def customer_delete(cid):
    try:
        query('DELETE FROM customer WHERE customerID=%s', (cid,), commit=True)
        flash('Customer deleted.', 'success')
    except Exception as e:
        flash(f'Cannot delete — customer may have existing appointments. ({e})', 'danger')
    return redirect(url_for('customers'))


# ---------------------------------------------------------------------------
# Appointments
# ---------------------------------------------------------------------------

@app.route('/appointments')
@login_required
def appointments():
    date_filter = request.args.get('date', '').strip()
    tech_filter = request.args.get('technician', '').strip()

    if is_customer():
        rows = call_customer_procedure('CALL customer_view_appointments()')
        if date_filter:
            rows = [row for row in rows if str(row['appointment_date']) == date_filter]
        return render_template('appointments.html',
            appointments=rows,
            technicians=[],
            date_filter=date_filter,
            tech_filter='',
        )

    sql = '''
        SELECT a.appointmentID, c.customer_name, c.customerID,
               a.appointment_date,
               GROUP_CONCAT(o.service_name ORDER BY o.service_name SEPARATOR ", ") AS services,
               p.cost, t.technician_name, t.technicianID
        FROM appointment a
        JOIN customer c ON a.customerID = c.customerID
        LEFT JOIN purchase p ON a.purchaseID = p.purchaseID
        LEFT JOIN orders o ON a.appointmentID = o.appointmentID
        LEFT JOIN schedules s ON a.appointmentID = s.appointmentID
        LEFT JOIN technician t ON s.technicianID = t.technicianID
        WHERE 1=1
    '''
    args = []
    if date_filter:
        sql += ' AND a.appointment_date = %s'
        args.append(date_filter)
    if tech_filter:
        sql += ' AND s.technicianID = %s'
        args.append(tech_filter)
    sql += ' GROUP BY a.appointmentID, c.customer_name, c.customerID, a.appointment_date, p.cost, t.technician_name, t.technicianID'
    sql += ' ORDER BY a.appointment_date DESC, a.appointmentID DESC'

    rows = query(sql, args)
    technicians = query('SELECT * FROM technician ORDER BY technician_name')
    return render_template('appointments.html',
        appointments=rows,
        technicians=technicians,
        date_filter=date_filter,
        tech_filter=tech_filter,
    )


@app.route('/appointments/add', methods=['GET', 'POST'])
@login_required
def appointment_add():
    if is_customer():
        customers_list = []
        services_list = call_customer_procedure('CALL customer_view_services()')
        technicians_list = []
    else:
        customers_list  = query('SELECT * FROM customer ORDER BY customer_name')
        services_list   = query('SELECT * FROM service ORDER BY service_name')
        technicians_list = query('SELECT * FROM technician ORDER BY technician_name')

    if request.method == 'POST':
        if is_customer():
            appt_date = request.form['appointment_date']
            conn = get_db(customer=True, customer_id=current_customer_id())
            try:
                with conn.cursor() as cur:
                    cur.execute('CALL customer_book_appointment(%s, @new_appointment_id)', (appt_date,))
                    clear_result_sets(cur)
                    cur.execute('SELECT @new_appointment_id AS appointmentID')
                    cur.fetchone()
                conn.commit()
                flash('Appointment booked successfully!', 'success')
                return redirect(url_for('appointments'))
            except Exception as e:
                conn.rollback()
                flash(f'Error booking appointment: {e}', 'danger')
            finally:
                conn.close()

        cid          = int(request.form['customerID'])
        service_name = request.form['service_name']
        tech_id      = int(request.form['technicianID'])
        appt_date    = request.form['appointment_date']

        # Look up service cost
        svc = query('SELECT service_cost FROM service WHERE service_name=%s', (service_name,), one=True)
        cost = float(svc['service_cost']) if svc else 0.0

        import pymysql
        conn = __import__('db').get_db()
        try:
            with conn.cursor() as cur:
                # 1. purchase
                cur.execute(
                    'INSERT INTO purchase (customerID, cost, purchase_date) VALUES (%s,%s,%s)',
                    (cid, cost, appt_date)
                )
                purchase_id = cur.lastrowid
                # 2. appointment
                cur.execute(
                    'INSERT INTO appointment (customerID, purchaseID, appointment_date) VALUES (%s,%s,%s)',
                    (cid, purchase_id, appt_date)
                )
                appt_id = cur.lastrowid
                # 3. orders
                cur.execute('INSERT INTO orders (service_name, appointmentID) VALUES (%s,%s)',
                            (service_name, appt_id))
                # 4. schedules
                cur.execute('INSERT INTO schedules (technicianID, appointmentID) VALUES (%s,%s)',
                            (tech_id, appt_id))
            conn.commit()
            flash('Appointment booked successfully!', 'success')
            return redirect(url_for('appointments'))
        except Exception as e:
            conn.rollback()
            flash(f'Error booking appointment: {e}', 'danger')
        finally:
            conn.close()

    return render_template('appointment_new.html',
        customers=customers_list,
        services=services_list,
        technicians=technicians_list,
        today=date.today().isoformat(),
    )


@app.route('/appointments/<int:aid>/delete', methods=['POST'])
@admin_required
def appointment_delete(aid):
    import pymysql
    conn = __import__('db').get_db()
    try:
        with conn.cursor() as cur:
            # Get purchaseID first
            cur.execute('SELECT purchaseID FROM appointment WHERE appointmentID=%s', (aid,))
            row = cur.fetchone()
            purchase_id = row['purchaseID'] if row else None
            cur.execute('DELETE FROM orders WHERE appointmentID=%s', (aid,))
            cur.execute('DELETE FROM schedules WHERE appointmentID=%s', (aid,))
            cur.execute('DELETE FROM appointment WHERE appointmentID=%s', (aid,))
            if purchase_id:
                cur.execute('DELETE FROM purchase WHERE purchaseID=%s', (purchase_id,))
        conn.commit()
        flash('Appointment cancelled.', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('appointments'))


# ---------------------------------------------------------------------------
# Purchases
# ---------------------------------------------------------------------------

@app.route('/purchases')
@login_required
def purchases():
    if is_customer():
        rows = call_customer_procedure('CALL customer_view_purchases()')
    else:
        rows = query(
            '''SELECT p.purchaseID, p.customerID, c.customer_name, p.cost, p.purchase_date
               FROM purchase p
               JOIN customer c ON p.customerID = c.customerID
               ORDER BY p.purchase_date DESC, p.purchaseID DESC'''
        )
    return render_template('purchases.html', purchases=rows)


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

@app.route('/services')
@login_required
def services():
    if is_customer():
        rows = call_customer_procedure('CALL customer_view_services()')
    else:
        rows = query('SELECT * FROM service ORDER BY service_name')
    return render_template('services.html', services=rows)


@app.route('/services/add', methods=['POST'])
@admin_required
def service_add():
    name = request.form['service_name'].strip()
    cost = request.form['service_cost'].strip()
    try:
        query('INSERT INTO service (service_name, service_cost) VALUES (%s,%s)',
              (name, cost), commit=True)
        flash(f'Service "{name}" added.', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('services'))


@app.route('/services/<path:name>/delete', methods=['POST'])
@admin_required
def service_delete(name):
    try:
        query('DELETE FROM service WHERE service_name=%s', (name,), commit=True)
        flash(f'Service deleted.', 'success')
    except Exception as e:
        flash(f'Cannot delete — service may be linked to appointments.', 'danger')
    return redirect(url_for('services'))


# ---------------------------------------------------------------------------
# Products / Inventory
# ---------------------------------------------------------------------------

@app.route('/products')
@admin_required
def products():
    type_filter = request.args.get('type', '').strip()
    if type_filter:
        rows = query(
            'SELECT * FROM product WHERE product_type=%s ORDER BY product_name',
            (type_filter,)
        )
    else:
        rows = query('SELECT * FROM product ORDER BY product_type, product_name')
    types = query('SELECT DISTINCT product_type FROM product ORDER BY product_type')
    return render_template('products.html', products=rows, types=types, type_filter=type_filter)


@app.route('/products/update', methods=['POST'])
@admin_required
def product_update():
    name     = request.form['product_name']
    new_qty  = request.form['stock_quantity']
    try:
        query('UPDATE product SET stock_quantity=%s WHERE product_name=%s',
              (new_qty, name), commit=True)
        flash(f'Stock for "{name}" updated to {new_qty}.', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('products'))


@app.route('/products/add', methods=['POST'])
@admin_required
def product_add():
    name  = request.form['product_name'].strip()
    qty   = request.form['stock_quantity'].strip()
    ptype = request.form['product_type'].strip()
    try:
        query('INSERT INTO product (product_name, stock_quantity, product_type) VALUES (%s,%s,%s)',
              (name, qty, ptype), commit=True)
        flash(f'Product "{name}" added.', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('products'))


@app.route('/products/<path:name>/delete', methods=['POST'])
@admin_required
def product_delete(name):
    try:
        query('DELETE FROM product WHERE product_name=%s', (name,), commit=True)
        flash(f'Product deleted.', 'success')
    except Exception as e:
        flash(f'Cannot delete — product may be in use.', 'danger')
    return redirect(url_for('products'))


# ---------------------------------------------------------------------------
# Technicians
# ---------------------------------------------------------------------------

@app.route('/technicians')
@admin_required
def technicians():
    rows = query(
        '''SELECT t.technicianID, t.technician_name, t.phone,
                  COUNT(DISTINCT s.appointmentID) AS total_appts
           FROM technician t
           LEFT JOIN schedules s ON t.technicianID = s.technicianID
           GROUP BY t.technicianID, t.technician_name, t.phone
           ORDER BY t.technician_name'''
    )
    return render_template('technicians.html', technicians=rows)


@app.route('/technicians/add', methods=['POST'])
@admin_required
def technician_add():
    name  = request.form['technician_name'].strip()
    phone = request.form['phone'].strip()
    try:
        query('INSERT INTO technician (technician_name, phone) VALUES (%s,%s)',
              (name, phone), commit=True)
        flash(f'Technician "{name}" added.', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('technicians'))


@app.route('/technicians/<int:tid>/delete', methods=['POST'])
@admin_required
def technician_delete(tid):
    try:
        query('DELETE FROM technician WHERE technicianID=%s', (tid,), commit=True)
        flash('Technician removed.', 'success')
    except Exception as e:
        flash(f'Cannot delete — technician may have scheduled appointments.', 'danger')
    return redirect(url_for('technicians'))


# ---------------------------------------------------------------------------
# Supply Orders
# ---------------------------------------------------------------------------

@app.route('/supply-orders')
@admin_required
def supply_orders():
    orders = query(
        '''SELECT so.orderID, so.order_date, so.delivery_date, so.cost,
                  sup.supplier_name, sup.city
           FROM supply_order so
           JOIN supplier sup ON so.supplierID = sup.supplierID
           ORDER BY so.order_date DESC'''
    )
    suppliers = query('SELECT * FROM supplier ORDER BY supplier_name')
    return render_template('supply_orders.html', orders=orders, suppliers=suppliers)


@app.route('/supply-orders/add', methods=['POST'])
@admin_required
def supply_order_add():
    supplier_id   = request.form['supplierID']
    cost          = request.form['cost']
    order_date    = request.form['order_date']
    delivery_date = request.form['delivery_date']
    try:
        query(
            'INSERT INTO supply_order (supplierID, cost, order_date, delivery_date) VALUES (%s,%s,%s,%s)',
            (supplier_id, cost, order_date, delivery_date), commit=True
        )
        flash('Supply order added.', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('supply_orders'))


# ---------------------------------------------------------------------------
# Export (CSV)
# ---------------------------------------------------------------------------

@app.route('/export/appointments')
@admin_required
def export_appointments():
    rows = query(
        '''SELECT a.appointmentID, c.customer_name, c.phone_number,
                  a.appointment_date,
                  GROUP_CONCAT(o.service_name ORDER BY o.service_name SEPARATOR "; ") AS services,
                  p.cost, t.technician_name
           FROM appointment a
           JOIN customer c ON a.customerID = c.customerID
           LEFT JOIN purchase p ON a.purchaseID = p.purchaseID
           LEFT JOIN orders o ON a.appointmentID = o.appointmentID
           LEFT JOIN schedules s ON a.appointmentID = s.appointmentID
           LEFT JOIN technician t ON s.technicianID = t.technicianID
           GROUP BY a.appointmentID, c.customer_name, c.phone_number,
                    a.appointment_date, p.cost, t.technician_name
           ORDER BY a.appointment_date DESC'''
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Appointment ID', 'Customer', 'Phone', 'Date', 'Services', 'Cost', 'Technician'])
    for r in rows:
        writer.writerow([r['appointmentID'], r['customer_name'], r['phone_number'],
                         r['appointment_date'], r['services'], r['cost'], r['technician_name']])
    output.seek(0)
    return Response(output, mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=appointments.csv'})


@app.route('/export/customers')
@admin_required
def export_customers():
    rows = query('SELECT * FROM customer ORDER BY customer_name')
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Customer ID', 'Name', 'Phone'])
    for r in rows:
        writer.writerow([r['customerID'], r['customer_name'], r['phone_number']])
    output.seek(0)
    return Response(output, mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=customers.csv'})


# ---------------------------------------------------------------------------
# Stored procedure demo (advanced SQL)
# ---------------------------------------------------------------------------

@app.route('/reports/tech-appointments')
@admin_required
def tech_appointments_report():
    technicians_list = query('SELECT * FROM technician ORDER BY technician_name')
    result = None
    tech_name = None
    selected_tech = request.args.get('technicianID', '')
    selected_month = request.args.get('month', str(date.today().month))

    if selected_tech:
        conn = __import__('db').get_db()
        try:
            with conn.cursor() as cur:
                cur.execute('CALL countTechAppointmentsMonth(%s, %s, @result)',
                            (selected_tech, selected_month))
                cur.execute('SELECT @result AS total')
                result = cur.fetchone()['total']
                t = query('SELECT technician_name FROM technician WHERE technicianID=%s',
                          (selected_tech,), one=True)
                tech_name = t['technician_name'] if t else ''
        finally:
            conn.close()

    return render_template('tech_report.html',
        technicians=technicians_list,
        result=result,
        tech_name=tech_name,
        selected_tech=selected_tech,
        selected_month=selected_month,
        months=[(str(i), datetime(2026,i,1).strftime('%B')) for i in range(1,13)],
    )


if __name__ == '__main__':
    app.run(debug=True, port=5000)
