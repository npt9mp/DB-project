DB_HOST     = 'mysql01.cs.virginia.edu'
DB_USER     = 'npt9mp'
DB_PASSWORD = '23Corkscrews?'
DB_NAME     = 'npt9mp'

# Fallback for the shared UVA MySQL server: your account cannot CREATE USER,
# so customer procedure calls use the same DB login as the main app.
CUSTOMER_DB_USER = DB_USER
CUSTOMER_DB_PASSWORD = DB_PASSWORD

SECRET_KEY  = 'nail-salon-cs4750-secret-2026'

# Simple hardcoded admin for MVP (replace with DB users table later)
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'
