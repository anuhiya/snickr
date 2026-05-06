import psycopg2

def get_connection():
    conn = psycopg2.connect(
        host="db.ucrlioksdxvdxwdmqvzy.supabase.co",
        database="postgres",
        user="postgres",
        password="Snickr2026!",
        port=5432,
        sslmode="require"
    )
    return conn