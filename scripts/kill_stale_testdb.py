from django.db import connection

cur = connection.cursor()
cur.execute(
    "SELECT pid, usename, application_name, state FROM pg_stat_activity "
    "WHERE datname='test_bbcc' AND pid <> pg_backend_pid()"
)
rows = cur.fetchall()
print("stale sessions:", rows)
for r in rows:
    cur.execute("SELECT pg_terminate_backend(%s)", [r[0]])
print("terminated:", len(rows))
