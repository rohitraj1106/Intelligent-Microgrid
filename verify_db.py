import sqlite3

conn = sqlite3.connect('data/home_101.db')
cur = conn.cursor()

# Row counts
print("=" * 55)
print("  DATABASE VERIFICATION — data/home_101.db")
print("=" * 55)
for table in ['telemetry', 'battery_state', 'solar_generation', 'load_history']:
    cur.execute(f'SELECT COUNT(*) FROM {table}')
    print(f"  {table:20s}: {cur.fetchone()[0]} rows")

print()
print("=" * 55)
print("  KEY TIME POINTS (24-hour profile)")
print("=" * 55)
cur.execute("SELECT timestamp, solar_w, load_w, battery_soc FROM telemetry ORDER BY timestamp")
rows = cur.fetchall()
for r in rows:
    ts, solar, load, soc = r
    marker = ""
    if solar > 0: marker += " SUN"
    if load > 1000: marker += " PEAK"
    if soc < 15: marker += " LOW_BAT"
    print(f"  {ts} | Solar:{solar:7.1f}W | Load:{load:7.1f}W | SoC:{soc:5.1f}%{marker}")

conn.close()
print()
print("Done!")
