import sqlite3

conn = sqlite3.connect('think_studio.db')
c = conn.cursor()

# Insert Janith Mihira into users table
c.execute("""
INSERT OR REPLACE INTO users (
    id, name, email, phone, role, org, package_name, package_cost, total_hours, used_hours, remaining_hours, start_date, end_date, balance_due
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    'u-janith', 'Janith Mihira', 'janith.mihira@gmail.com', '0712345678', 'customer', 'Think Studio Client',
    'One-Time Recording Session', 2000.0, 2.0, 1.0, 1.0, '2026-09-29', '2026-10-29', 2000.0
))

# Insert Janith's One-Time Recording Session booking
c.execute("""
INSERT OR REPLACE INTO bookings (
    id, user_email, user_name, date, time, duration, topic, gear, zoom_link, meeting_id, passcode, status
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    'B-JAN-REC01', 'janith.mihira@gmail.com', 'Janith Mihira',
    '2026-09-29', '02:00 PM – 04:00 PM', 2.0,
    'One-Time Studio Video Recording Session',
    '4K Cinema Camera + Studio Acoustics + Teleprompter',
    '', '', '', 'Confirmed'
))

conn.commit()
print('SUCCESS: Added Janith Mihira to SQLite DB!')
conn.close()
