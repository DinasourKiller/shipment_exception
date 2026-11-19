import psycopg2

conn = psycopg2.connect("host=localhost port=5432 user=postgres password=root dbname=Shipment")
cur = conn.cursor()

cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
tables = [t[0] for t in cur.fetchall()]
print("Tables in Shipment DB:", tables)

for t in ["users", "refresh_tokens", "login_attempts"]:
    cur.execute(f"SELECT count(*) FROM {t}")
    print(f"  {t}: {cur.fetchone()[0]} rows")

cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='users' ORDER BY ordinal_position")
print("\nusers table columns:")
for col, dtype in cur.fetchall():
    print(f"  {col}: {dtype}")

conn.close()
