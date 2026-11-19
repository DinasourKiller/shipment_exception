import psycopg2

conn = psycopg2.connect("host=localhost port=5432 user=postgres password=root dbname=Shipment")
cur = conn.cursor()

cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
tables = [t[0] for t in cur.fetchall()]
print(f"Total Tables in Shipment Database ({len(tables)}):")
for t in tables:
    cur.execute(f"SELECT count(*) FROM {t}")
    count = cur.fetchone()[0]
    print(f"  - {t:<25} ({count} rows)")

conn.close()
