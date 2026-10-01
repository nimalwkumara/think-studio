import sqlite3

conn = sqlite3.connect('think_studio.db')
c = conn.cursor()

# 1. Update Menuka in users table
c.execute("""
UPDATE users SET 
    package_name = 'Hourly Studio Flex (2h = Rs.3,000)',
    package_cost = 11000.0,
    total_hours = 8.0,
    used_hours = 3.0,
    remaining_hours = 5.0,
    balance_due = 4000.0
WHERE id = 'u-menuka' OR email = 'menuka.wijebandara@gmail.com'
""")

# 2. Payments: Remove the tentative 1000 payment, keep the verified 7000 payment
c.execute("DELETE FROM payments WHERE id = 'PAY-MEN-1000'")

c.execute("""
INSERT OR REPLACE INTO payments (
    id, user_email, user_name, amount, ref, method, date, status, slip_filename
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    'PAY-MEN-7000', 'menuka.wijebandara@gmail.com', 'Menuka Wijebandara',
    7000.0, 'PB-MEN-7000', 'People\'s Bank Godakawela', '2026-09-21', 'Verified', 'menuka_slip.png'
))

# 3. Add Menuka's bookings: 21 Sep (2 hours) and 29 Sep today (1 hour)
c.execute("""
INSERT OR REPLACE INTO bookings (
    id, user_email, user_name, date, time, duration, topic, gear, zoom_link, meeting_id, passcode, status
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    'B-MEN-SEP21', 'menuka.wijebandara@gmail.com', 'Menuka Wijebandara',
    '2026-09-21', '03:00 PM – 05:00 PM', 2.0,
    'Studio Lecture Session (2 Hours)',
    '75" Smart Board + Studio Mic',
    'https://zoom.us/j/84523194022?pwd=THINKSTUDIO2026', '845 2319 4022', 'THINK2026', 'Completed'
))

c.execute("""
INSERT OR REPLACE INTO bookings (
    id, user_email, user_name, date, time, duration, topic, gear, zoom_link, meeting_id, passcode, status
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    'B-MEN-SEP29', 'menuka.wijebandara@gmail.com', 'Menuka Wijebandara',
    '2026-09-29', '05:00 PM – 06:00 PM', 1.0,
    'Studio Quick Session (1 Hour)',
    '75" Smart Board + Studio Mic',
    'https://zoom.us/j/84523194022?pwd=THINKSTUDIO2026', '845 2319 4022', 'THINK2026', 'Completed'
))

conn.commit()
print('SUCCESS: Updated Menuka Wijebandara financial & booking records in SQLite!')
conn.close()
