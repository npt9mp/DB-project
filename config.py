DB_HOST     = 'mysql01.cs.virginia.edu'
DB_USER     = 'npt9mp'
DB_PASSWORD = '23Corkscrews?'
DB_NAME     = 'npt9mp'

# Restricted sub-account for end-user (customer) database connections.
# npt9mp_a is granted EXECUTE-only on the five customer stored procedures,
# so customers cannot directly read or modify any table.
CUSTOMER_DB_USER     = 'npt9mp_a'
CUSTOMER_DB_PASSWORD = 'Winter2026'

SECRET_KEY  = 'nail-salon-cs4750-secret-2026'

# Simple hardcoded admin for MVP (replace with DB users table later)
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'
