import sqlite3

conn = sqlite3.connect('think_studio.db')
c = conn.cursor()

# 1. Update Kavindya's User Details
c.execute("""
UPDATE users SET 
    package_name = 'Studio Master Session (6.00 PM – 9.00 PM)',
    package_cost = 15000.0,
    total_hours = 6.0,
    used_hours = 0.0,
    remaining_hours = 6.0,
    start_date = '2026-09-26',
    end_date = '2026-10-31',
    balance_due = 0.0
WHERE id = 'u-kavindya' OR email = 'kavindya.kodithuwakku@gmail.com'
""")

# 2. Update Payment Date to 2026-09-26
c.execute("""
UPDATE payments SET 
    date = '2026-09-26',
    amount = 15000.0,
    ref = 'PB-KAV-15000',
    method = 'Peoples Bank Godakawela'
WHERE id = 'PAY-KAV-15000' OR user_name = 'Kavindya Kodithuwakku'
""")

# 3. Insert Kavindya's Studio Bookings for 3 Oct & 4 Oct (6:00 PM - 9:00 PM)
c.execute("""
INSERT OR REPLACE INTO bookings (
    id, user_email, user_name, date, time, duration, topic, gear, zoom_link, meeting_id, passcode, status
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    'B-KAV-OCT03', 'kavindya.kodithuwakku@gmail.com', 'Kavindya Kodithuwakku',
    '2026-10-03', '06:00 PM – 09:00 PM', 3.0,
    'Studio Masterclass Live Session Day 1',
    '75" 4K Smart Board + Studio Acoustics + Zoom',
    'https://zoom.us/j/84523194022?pwd=THINKSTUDIO2026',
    '845 2319 4022', 'THINK2026', 'Confirmed'
))

c.execute("""
INSERT OR REPLACE INTO bookings (
    id, user_email, user_name, date, time, duration, topic, gear, zoom_link, meeting_id, passcode, status
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    'B-KAV-OCT04', 'kavindya.kodithuwakku@gmail.com', 'Kavindya Kodithuwakku',
    '2026-10-04', '06:00 PM – 09:00 PM', 3.0,
    'Studio Masterclass Live Session Day 2 (Sunday)',
    '75" 4K Smart Board + Confidence Monitors + Zoom',
    'https://zoom.us/j/84523194022?pwd=THINKSTUDIO2026',
    '845 2319 4022', 'THINK2026', 'Confirmed'
))

conn.commit()
print('SUCCESS: Updated Kavindya details, payment date 2026-09-26, and Oct 3/4 bookings!')
conn.close()
