import http.server
import socketserver
import json
import sqlite3
import os
import sys
import time
import threading
import urllib.request
import mimetypes
from urllib.parse import urlparse

sys.stdout.reconfigure(line_buffering=True)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'think_studio.db')
PORT = int(os.environ.get('PORT', 8000))

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # 1. Users Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'customer',
            org TEXT DEFAULT '',
            package_name TEXT DEFAULT 'Monthly Package',
            package_cost REAL DEFAULT 12000,
            total_hours REAL DEFAULT 20,
            used_hours REAL DEFAULT 8,
            remaining_hours REAL DEFAULT 12,
            start_date TEXT DEFAULT '2026-09-15',
            end_date TEXT DEFAULT '2026-10-15',
            balance_due REAL DEFAULT 4000
        )
    ''')

    # 2. Payments Table (Real Persistent Storage for User and Admin)
    c.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id TEXT PRIMARY KEY,
            user_email TEXT NOT NULL,
            user_name TEXT NOT NULL,
            amount REAL NOT NULL,
            ref TEXT NOT NULL,
            method TEXT DEFAULT 'People''s Bank Transfer',
            date TEXT NOT NULL,
            status TEXT DEFAULT 'Pending Verification',
            slip_filename TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 3. Bookings Table (With Zoom Meeting Links)
    c.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id TEXT PRIMARY KEY,
            user_email TEXT NOT NULL,
            user_name TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            duration REAL NOT NULL,
            topic TEXT NOT NULL,
            gear TEXT NOT NULL,
            zoom_link TEXT DEFAULT '',
            meeting_id TEXT DEFAULT '',
            passcode TEXT DEFAULT '',
            status TEXT DEFAULT 'Confirmed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 4. Reviews Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id TEXT PRIMARY KEY,
            author TEXT NOT NULL,
            role TEXT NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT NOT NULL,
            featured INTEGER DEFAULT 1,
            status TEXT DEFAULT 'Approved',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 5. Settings Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')

    # Seed initial data if users is empty
    c.execute('SELECT COUNT(*) FROM users')
    if c.fetchone()[0] == 0:
        c.execute('''
            INSERT INTO users (id, name, email, phone, role, org, package_name, package_cost, total_hours, used_hours, remaining_hours, start_date, end_date, balance_due)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            'u-1', 'Dr. Rajesh Sharma', 'dr.rajesh@gmail.com', '+94 77 123 4567', 'customer',
            'Apex Physics Academy', 'Monthly Package', 12000, 20, 8, 12, '2026-09-15', '2026-10-15', 4000
        ))
        c.execute('''
            INSERT INTO users (id, name, email, phone, role, org, package_name, package_cost, total_hours, used_hours, remaining_hours, start_date, end_date, balance_due)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            'admin-1', 'Studio Manager', 'thinkstudiocontact@gmail.com', '0702663137', 'admin',
            'Think Studio Management', '', 0, 0, 0, 0, '', '', 0
        ))

        # Seed Payments
        c.execute('''
            INSERT INTO payments (id, user_email, user_name, amount, ref, method, date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('P-101', 'dr.rajesh@gmail.com', 'Dr. Rajesh Sharma', 8000, 'PB-773921', 'People''s Bank Transfer', '2026-09-15', 'Verified'))
        
        c.execute('''
            INSERT INTO payments (id, user_email, user_name, amount, ref, method, date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('SLIP-901', 'dr.rajesh@gmail.com', 'Dr. Rajesh Sharma', 4000, 'PB-8942188', 'People''s Bank Godakawela', '2026-09-28', 'Pending Verification'))

        # Seed Bookings
        c.execute('''
            INSERT INTO bookings (id, user_email, user_name, date, time, duration, topic, gear, zoom_link, meeting_id, passcode, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            'B-201', 'dr.rajesh@gmail.com', 'Dr. Rajesh Sharma', '2026-09-29', '10:00 AM – 12:00 PM', 2,
            'Electromagnetism Live Batch', '75" Smart Board + Zoom Rig',
            'https://zoom.us/j/84523194022?pwd=THINKSTUDIO2026', '845 2319 4022', 'THINK2026', 'Confirmed'
        ))
        c.execute('''
            INSERT INTO bookings (id, user_email, user_name, date, time, duration, topic, gear, zoom_link, meeting_id, passcode, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            'B-202', 'dr.rajesh@gmail.com', 'Dr. Rajesh Sharma', '2026-09-25', '02:00 PM – 05:00 PM', 3,
            'Wave Optics Masterclass Module 1', '75" Smart Board',
            'https://zoom.us/j/84523194022?pwd=THINKSTUDIO2026', '845 2319 4022', 'THINK2026', 'Completed'
        ))

        # Seed Reviews
        c.execute('''
            INSERT INTO reviews (id, author, role, rating, comment, featured, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            'r-1', 'Dr. Rajesh Sharma', 'Physics Lecturer & Author', 5,
            'The 75-inch smart board with integrated Zoom allows me to see my students on the confidence monitors while writing equations smoothly. Sound acoustics are 10/10.',
            1, 'Approved'
        ))

        # Studio Bank Settings
        bank_info = json.dumps({
            "accountName": "E.M.S.S. Fonseka",
            "bankName": "People's Bank",
            "branch": "Godakawela Branch",
            "accountNumber": "245200290056879",
            "phone": "0702663137",
            "email": "thinkstudiocontact@gmail.com"
        })
        c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('studioBank', bank_info))

    # Always ensure Google Sheet Webhook URL is registered
    c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (
        'googleSheetWebhook',
        'https://script.google.com/macros/s/AKfycbxLeyn0FBSFH6AGSIG_SoEXWMPmb1Pu5HTz5-uXgljJkF1ePSa8b2Dg-_F0QzjdSjx0/exec'
    ))

    # Always ensure Google OAuth Client ID setting exists
    c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ('googleClientId', ''))

    # Schema migration: Add avatar and google_id columns to users if missing
    try:
        c.execute('ALTER TABLE users ADD COLUMN avatar TEXT DEFAULT ""')
    except Exception:
        pass
    try:
        c.execute('ALTER TABLE users ADD COLUMN google_id TEXT DEFAULT ""')
    except Exception:
        pass

    conn.commit()
    conn.close()

def sync_user_to_google_sheet(user_dict, event_type="sync_user", payment_info=None):
    """Syncs user details, package hours, balances, and monthly payments to Google Sheet asynchronously"""
    def _do_sync():
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute('SELECT value FROM settings WHERE key = "googleSheetWebhook"')
            row = c.fetchone()
            conn.close()
            webhook_url = row["value"] if row else ""
            if not webhook_url or not webhook_url.startswith("http"):
                return

            pkg_name = user_dict.get("packageName") or user_dict.get("package_name") or (user_dict.get("package", {}).get("name") if isinstance(user_dict.get("package"), dict) else "Monthly Package")
            total_h = float(user_dict.get("totalHours") or user_dict.get("total_hours") or (user_dict.get("package", {}).get("totalHours") if isinstance(user_dict.get("package"), dict) else 20))
            rem_h = float(user_dict.get("remainingHours") if "remainingHours" in user_dict else user_dict.get("remaining_hours", (user_dict.get("package", {}).get("remainingHours") if isinstance(user_dict.get("package"), dict) else 12)))
            used_h = float(user_dict.get("usedHours") if "usedHours" in user_dict else user_dict.get("used_hours", max(0, total_h - rem_h)))
            bal_due = float(user_dict.get("balanceDue") if "balanceDue" in user_dict else user_dict.get("balance_due", 0))
            pkg_price = float(user_dict.get("packagePrice") or user_dict.get("package_cost") or (user_dict.get("package", {}).get("cost") if isinstance(user_dict.get("package"), dict) else 12000))
            paid_amt = max(0, pkg_price - bal_due)
            status = "Active" if rem_h > 0 else "Expired"

            from datetime import datetime
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            month_str = datetime.now().strftime("%B %Y")

            payload = {
                "action": event_type,
                "timestamp": now_str,
                "month": month_str,
                "id": user_dict.get("id", ""),
                "name": user_dict.get("name", ""),
                "email": user_dict.get("email", ""),
                "phone": user_dict.get("phone", ""),
                "packageName": pkg_name,
                "packagePrice": pkg_price,
                "paidAmount": paid_amt,
                "balanceDue": bal_due,
                "totalHours": total_h,
                "usedHours": used_h,
                "remainingHours": rem_h,
                "status": status,
                "org": user_dict.get("org", "")
            }

            if payment_info:
                payload["payment"] = payment_info

            req = urllib.request.Request(
                webhook_url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                print(f"[*] Google Sheet synced user: {payload['name']} ({payload['email']}) -> HTTP {resp.status}")
        except Exception as e:
            print(f"[!] Google Sheet sync notice: {e}")

    threading.Thread(target=_do_sync, daemon=True).start()

def get_full_state():
    conn = get_db()
    c = conn.cursor()
    
    # Users
    c.execute('SELECT * FROM users')
    raw_users = c.fetchall()
    users = []
    for u in raw_users:
        u_dict = dict(u)
        user_dict = {
            "id": u["id"],
            "name": u["name"],
            "email": u["email"],
            "phone": u["phone"],
            "role": u["role"],
            "org": u["org"],
            "avatar": u_dict.get("avatar") or ""
        }
        if u["role"] == "customer":
            user_dict["package"] = {
                "name": u["package_name"],
                "cost": u["package_cost"],
                "totalHours": u["total_hours"],
                "usedHours": u["used_hours"],
                "remainingHours": u["remaining_hours"],
                "startDate": u["start_date"],
                "endDate": u["end_date"]
            }
            # Fetch verified payments for user
            c.execute('SELECT * FROM payments WHERE user_email = ? AND status = "Verified" ORDER BY date DESC', (u["email"],))
            user_dict["payments"] = [dict(p) for p in c.fetchall()]
            user_dict["balanceDue"] = u["balance_due"]
        users.append(user_dict)
    
    # Bookings
    c.execute('SELECT * FROM bookings ORDER BY date DESC')
    bookings = []
    for b in c.fetchall():
        bookings.append({
            "id": b["id"],
            "userEmail": b["user_email"],
            "userName": b["user_name"],
            "date": b["date"],
            "time": b["time"],
            "duration": b["duration"],
            "topic": b["topic"],
            "gear": b["gear"],
            "zoomLink": b["zoom_link"],
            "meetingId": b["meeting_id"],
            "passcode": b["passcode"],
            "status": b["status"]
        })
    
    # Reviews
    c.execute('SELECT * FROM reviews WHERE status = "Approved" ORDER BY created_at DESC')
    reviews = [dict(r) for r in c.fetchall()]

    # Pending Slips
    c.execute('SELECT * FROM payments WHERE status = "Pending Verification" ORDER BY date DESC')
    pending_slips = []
    for p in c.fetchall():
        pending_slips.append({
            "id": p["id"],
            "userEmail": p["user_email"],
            "userName": p["user_name"],
            "amount": p["amount"],
            "ref": p["ref"],
            "date": p["date"],
            "status": p["status"],
            "method": p["method"]
        })
    
    # All Payments (for admin ledger)
    c.execute('SELECT * FROM payments ORDER BY date DESC')
    all_payments = [dict(p) for p in c.fetchall()]

    # Bank Settings
    c.execute('SELECT value FROM settings WHERE key = "studioBank"')
    sb_row = c.fetchone()
    studio_bank = json.loads(sb_row["value"]) if sb_row else {
        "accountName": "E.M.S.S. Fonseka",
        "bankName": "People's Bank",
        "branch": "Godakawela Branch",
        "accountNumber": "245200290056879",
        "phone": "0702663137",
        "email": "thinkstudiocontact@gmail.com"
    }

    # Google Sheet Webhook Settings
    c.execute('SELECT value FROM settings WHERE key = "googleSheetWebhook"')
    gsw_row = c.fetchone()
    google_sheet_webhook = gsw_row["value"] if gsw_row else "https://script.google.com/macros/s/AKfycbxLeyn0FBSFH6AGSIG_SoEXWMPmb1Pu5HTz5-uXgljJkF1ePSa8b2Dg-_F0QzjdSjx0/exec"

    # Google OAuth Settings
    c.execute('SELECT value FROM settings WHERE key = "googleClientId"')
    gci_row = c.fetchone()
    google_client_id = gci_row["value"] if gci_row else ""

    conn.close()
    return {
        "users": users,
        "bookings": bookings,
        "reviews": reviews,
        "pendingSlips": pending_slips,
        "allPayments": all_payments,
        "studioBank": studio_bank,
        "googleSheetWebhook": google_sheet_webhook,
        "googleClientId": google_client_id,
        "databaseType": "SQLite3 (Persistent Database)",
        "dbPath": DB_PATH
    }

class ThinkStudioHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def send_json(self, data, status_code=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/status':
            conn = get_db()
            c = conn.cursor()
            c.execute('SELECT COUNT(*) FROM payments')
            total_payments = c.fetchone()[0]
            c.execute('SELECT SUM(amount) FROM payments WHERE status = "Verified"')
            rev_row = c.fetchone()[0] or 0
            c.execute('SELECT COUNT(*) FROM payments WHERE status = "Pending Verification"')
            pending = c.fetchone()[0]
            c.execute('SELECT COUNT(*) FROM bookings')
            total_bookings = c.fetchone()[0]
            conn.close()

            resp = {
                "status": "connected",
                "database": "think_studio.db",
                "engine": "SQLite3",
                "metrics": {
                    "totalPayments": total_payments,
                    "verifiedRevenue": rev_row,
                    "pendingSlips": pending,
                    "totalBookings": total_bookings
                }
            }
            self.send_json(resp)
            return

        elif parsed.path == '/api/state':
            state = get_full_state()
            self.send_json(state)
            return

        # Serve static files (HTML, etc.)
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'
        
        try:
            payload = json.loads(post_data)
        except Exception:
            payload = {}

        conn = get_db()
        c = conn.cursor()

        # 1. New Payment / Slip Upload (Persistent DB Insertion)
        if parsed.path == '/api/payments':
            slip_id = payload.get('id') or f"SLIP-{int(time.time() * 1000)}"
            user_email = payload.get('userEmail')
            user_name = payload.get('userName', 'Customer')
            amount = float(payload.get('amount', 0))
            ref = payload.get('ref', 'N/A')
            method = payload.get('method', "People's Bank Godakawela")
            date = payload.get('date') or '2026-09-28'

            c.execute('''
                INSERT INTO payments (id, user_email, user_name, amount, ref, method, date, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending Verification')
            ''', (slip_id, user_email, user_name, amount, ref, method, date))
            conn.commit()
            conn.close()

            self.send_json({"success": True, "message": "Payment slip recorded in database", "slipId": slip_id})
            return

        # 2. Admin Verify Payment (Updates Status and Deducts Balance in SQLite)
        elif parsed.path == '/api/payments/verify':
            slip_id = payload.get('slipId')
            c.execute('SELECT * FROM payments WHERE id = ?', (slip_id,))
            slip = c.fetchone()
            if slip:
                amount = slip['amount']
                user_email = slip['user_email']

                # Update payment status
                c.execute('UPDATE payments SET status = "Verified" WHERE id = ?', (slip_id,))

                # Deduct balance due from user in DB
                c.execute('UPDATE users SET balance_due = MAX(0, balance_due - ?) WHERE email = ?', (amount, user_email))
                conn.commit()

                # Sync updated user balance & payment record to Google Sheet
                c.execute('SELECT * FROM users WHERE email = ?', (user_email,))
                u_row = c.fetchone()
                if u_row:
                    sync_user_to_google_sheet(dict(u_row), event_type="payment_verified", payment_info={
                        "id": slip["id"],
                        "userName": slip["user_name"],
                        "amount": slip["amount"],
                        "ref": slip["ref"],
                        "date": slip["date"],
                        "method": slip["method"],
                        "status": "Verified"
                    })

                conn.close()

                self.send_json({"success": True, "message": f"Payment {slip_id} verified in DB and balance updated"})
                return
            else:
                conn.close()
                self.send_json({"success": False, "error": "Slip not found"}, 404)
                return

        # 3. Admin Update Zoom Link for Booking (Persistent DB Update)
        elif parsed.path == '/api/bookings/update-zoom':
            booking_id = payload.get('bookingId')
            zoom_link = payload.get('zoomLink', '')
            meeting_id = payload.get('meetingId', '')
            passcode = payload.get('passcode', '')

            if booking_id == 'all':
                # Update all bookings
                c.execute('''
                    UPDATE bookings 
                    SET zoom_link = ?, meeting_id = ?, passcode = ?
                ''', (zoom_link, meeting_id, passcode))
            else:
                c.execute('''
                    UPDATE bookings 
                    SET zoom_link = ?, meeting_id = ?, passcode = ? 
                    WHERE id = ?
                ''', (zoom_link, meeting_id, passcode, booking_id))
            
            conn.commit()
            conn.close()

            self.send_json({"success": True, "message": "Zoom link saved in SQLite database"})
            return

        # 4. Create Booking
        elif parsed.path == '/api/bookings/create':
            b_id = payload.get('id') or f"B-{int(time.time() * 1000)}"
            user_email = payload.get('userEmail')
            user_name = payload.get('userName')
            date = payload.get('date')
            time_slot = payload.get('time')
            duration = float(payload.get('duration', 2))
            topic = payload.get('topic')
            gear = payload.get('gear')
            zoom_link = payload.get('zoomLink', '')
            meeting_id = payload.get('meetingId', '845 2319 4022')
            passcode = payload.get('passcode', 'THINK2026')

            c.execute('''
                INSERT INTO bookings (id, user_email, user_name, date, time, duration, topic, gear, zoom_link, meeting_id, passcode, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Confirmed')
            ''', (b_id, user_email, user_name, date, time_slot, duration, topic, gear, zoom_link, meeting_id, passcode))

            # Deduct hours from user package in DB
            c.execute('''
                UPDATE users 
                SET used_hours = used_hours + ?, remaining_hours = MAX(0, remaining_hours - ?)
                WHERE email = ?
            ''', (duration, duration, user_email))
            conn.commit()

            # Sync updated user hours to Google Sheet
            c.execute('SELECT * FROM users WHERE email = ?', (user_email,))
            u_row = c.fetchone()
            if u_row:
                sync_user_to_google_sheet(dict(u_row))

            conn.close()

            self.send_json({"success": True, "bookingId": b_id})
            return

        # 5. Admin Adjust Hours
        elif parsed.path == '/api/users/adjust-hours':
            user_email = payload.get('userEmail')
            delta = float(payload.get('delta', 0))
            c.execute('''
                UPDATE users 
                SET remaining_hours = MAX(0, remaining_hours + ?)
                WHERE email = ?
            ''', (delta, user_email))
            conn.commit()

            # Sync updated user hours to Google Sheet
            c.execute('SELECT * FROM users WHERE email = ?', (user_email,))
            u_row = c.fetchone()
            if u_row:
                sync_user_to_google_sheet(dict(u_row))

            conn.close()

            self.send_json({"success": True})
            return

        # 6. Save Google Sheet Webhook Settings
        elif parsed.path == '/api/settings/google-sheet':
            url = payload.get('webhookUrl', '').strip()
            c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES ("googleSheetWebhook", ?)', (url,))
            conn.commit()
            conn.close()
            self.send_json({"success": True, "message": "Google Sheet Webhook URL saved successfully", "webhookUrl": url})
            return

        # 7. Sync All Customers to Google Sheet
        elif parsed.path == '/api/sync/google-sheet':
            c.execute('SELECT * FROM users WHERE role = "customer"')
            customers = c.fetchall()
            synced_count = 0
            for u in customers:
                user_obj = {
                    "id": u["id"],
                    "name": u["name"],
                    "email": u["email"],
                    "phone": u["phone"],
                    "package_name": u["package_name"],
                    "total_hours": u["total_hours"],
                    "remaining_hours": u["remaining_hours"],
                    "balance_due": u["balance_due"],
                    "org": u["org"]
                }
                sync_user_to_google_sheet(user_obj)
                synced_count += 1
            conn.close()
            self.send_json({"success": True, "syncedCount": synced_count, "message": f"{synced_count} user(s) synced to Google Sheet"})
            return

        # 8. Register User
        elif parsed.path == '/api/users/register':
            u_id = payload.get('id') or f"u-{int(time.time() * 1000)}"
            name = payload.get('name', 'Customer')
            email = payload.get('email', '')
            phone = payload.get('phone', '')
            pkg = payload.get('package', {})
            pkg_name = pkg.get('name', 'Monthly Package')
            pkg_cost = float(pkg.get('cost', 12000))
            total_hours = float(pkg.get('totalHours', 20))
            used_hours = float(pkg.get('usedHours', 0))
            rem_hours = float(pkg.get('remainingHours', 20))
            start_date = pkg.get('startDate', '2026-09-28')
            end_date = pkg.get('endDate', '2026-10-28')
            balance_due = float(payload.get('balanceDue', 12000))
            org = payload.get('org', '')

            c.execute('''
                INSERT OR REPLACE INTO users (id, name, email, phone, role, org, package_name, package_cost, total_hours, used_hours, remaining_hours, start_date, end_date, balance_due)
                VALUES (?, ?, ?, ?, 'customer', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (u_id, name, email, phone, org, pkg_name, pkg_cost, total_hours, used_hours, rem_hours, start_date, end_date, balance_due))
            conn.commit()

            sync_user_to_google_sheet(payload)
            conn.close()
            self.send_json({"success": True, "userId": u_id, "message": "User registered and synced to Google Sheet"})
            return

        # 9. Cancel Booking & Restore Hours (in SQLite & Google Sheet)
        elif parsed.path == '/api/bookings/cancel':
            booking_id = payload.get('bookingId')
            c.execute('SELECT * FROM bookings WHERE id = ?', (booking_id,))
            b_row = c.fetchone()
            if b_row:
                user_email = b_row['user_email']
                duration = b_row['duration']
                c.execute('DELETE FROM bookings WHERE id = ?', (booking_id,))
                if payload.get('restoreHours', True):
                    c.execute('''
                        UPDATE users 
                        SET used_hours = MAX(0, used_hours - ?), remaining_hours = remaining_hours + ?
                        WHERE email = ?
                    ''', (duration, duration, user_email))
                conn.commit()

                c.execute('SELECT * FROM users WHERE email = ?', (user_email,))
                u_row = c.fetchone()
                if u_row:
                    sync_user_to_google_sheet(dict(u_row))

                conn.close()
                self.send_json({"success": True, "message": f"Booking {booking_id} cancelled and hours restored in database"})
                return
            else:
                conn.close()
                self.send_json({"success": False, "error": "Booking not found"}, 404)
                return

        # 10. Complete Booking
        elif parsed.path == '/api/bookings/complete':
            booking_id = payload.get('bookingId')
            c.execute('UPDATE bookings SET status = "Completed" WHERE id = ?', (booking_id,))
            conn.commit()
            conn.close()
            self.send_json({"success": True, "message": f"Booking {booking_id} completed"})
            return

        # 11. Add Review / Testimonial
        elif parsed.path == '/api/reviews':
            r_id = payload.get('id') or f"r-{int(time.time() * 1000)}"
            author = payload.get('author', 'Anonymous')
            role = payload.get('role', 'Client')
            rating = int(payload.get('rating', 5))
            comment = payload.get('comment', '')
            c.execute('''
                INSERT INTO reviews (id, author, role, rating, comment, featured, status)
                VALUES (?, ?, ?, ?, ?, 1, 'Approved')
            ''', (r_id, author, role, rating, comment))
            conn.commit()
            conn.close()
            self.send_json({"success": True, "reviewId": r_id, "message": "Review saved in SQLite database"})
            return

        # 12. Update User Profile
        elif parsed.path == '/api/users/update-profile':
            email = payload.get('email')
            name = payload.get('name')
            phone = payload.get('phone')
            c.execute('UPDATE users SET name = ?, phone = ? WHERE email = ?', (name, phone, email))
            conn.commit()
            c.execute('SELECT * FROM users WHERE email = ?', (email,))
            u_row = c.fetchone()
            if u_row:
                sync_user_to_google_sheet(dict(u_row))
            conn.close()
            self.send_json({"success": True, "message": "Profile updated in SQLite DB and synced to Google Sheet"})
            return

        # 13. Update Studio Bank Details
        elif parsed.path == '/api/settings/studio-bank':
            bank_data = {
                "accountName": payload.get('accountName', 'E.M.S.S. Fonseka'),
                "bankName": payload.get('bankName', "People's Bank"),
                "branch": payload.get('branch', 'Godakawela Branch'),
                "accountNumber": payload.get('accountNumber', '245200290056879'),
                "phone": payload.get('phone', '0702663137'),
                "email": payload.get('email', 'thinkstudiocontact@gmail.com')
            }
            c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES ("studioBank", ?)', (json.dumps(bank_data),))
            conn.commit()
            conn.close()
            self.send_json({"success": True, "message": "Studio bank details saved in SQLite database"})
            return

        # 14. Admin Reject Slip
        elif parsed.path == '/api/payments/reject':
            slip_id = payload.get('slipId')
            c.execute('UPDATE payments SET status = "Rejected" WHERE id = ?', (slip_id,))
            conn.commit()
            conn.close()
            self.send_json({"success": True, "message": f"Slip {slip_id} rejected"})
            return

        # 15. Google OAuth Sign-In & Upsert (SQLite + Google Sheets Sync)
        elif parsed.path == '/api/users/google-auth':
            email = payload.get('email', '').strip().lower()
            name = payload.get('name', '').strip() or 'Google User'
            avatar = payload.get('avatar', '').strip()
            google_id = payload.get('googleId', '').strip()

            if not email:
                conn.close()
                self.send_json({"success": False, "error": "Email is required"}, 400)
                return

            c.execute('SELECT * FROM users WHERE LOWER(email) = ?', (email,))
            existing = c.fetchone()

            if existing:
                u_row = dict(existing)
                # Update avatar & google_id if supplied
                if avatar:
                    try:
                        c.execute('UPDATE users SET avatar = ?, google_id = COALESCE(NULLIF(google_id, ""), ?) WHERE LOWER(email) = ?', (avatar, google_id, email))
                        conn.commit()
                        u_row['avatar'] = avatar
                    except Exception:
                        pass

                user_dict = {
                    "id": u_row["id"],
                    "name": u_row["name"],
                    "email": u_row["email"],
                    "phone": u_row["phone"],
                    "role": u_row["role"],
                    "org": u_row["org"],
                    "avatar": u_row.get("avatar") or avatar
                }
                if u_row["role"] == "customer":
                    user_dict["package"] = {
                        "name": u_row["package_name"],
                        "cost": u_row["package_cost"],
                        "totalHours": u_row["total_hours"],
                        "usedHours": u_row["used_hours"],
                        "remainingHours": u_row["remaining_hours"],
                        "startDate": u_row["start_date"],
                        "endDate": u_row["end_date"]
                    }
                    c.execute('SELECT * FROM payments WHERE LOWER(user_email) = ? AND status = "Verified" ORDER BY date DESC', (email,))
                    user_dict["payments"] = [dict(p) for p in c.fetchall()]
                    user_dict["balanceDue"] = u_row["balance_due"]

                conn.close()
                self.send_json({"success": True, "user": user_dict, "isNew": False, "message": f"Welcome back, {user_dict['name']}"})
                return
            else:
                role = "admin" if email in ['thinkstudiocontact@gmail.com', 'admin@thinkstudio.com'] else "customer"
                u_id = f"u-{int(time.time() * 1000)}"
                phone = payload.get('phone', '+94 70 000 0000')

                from datetime import datetime, timedelta
                now_d = datetime.now()
                end_d = now_d + timedelta(days=30)
                start_str = now_d.strftime("%Y-%m-%d")
                end_str = end_d.strftime("%Y-%m-%d")

                c.execute('''
                    INSERT INTO users (id, name, email, phone, role, org, package_name, package_cost, total_hours, used_hours, remaining_hours, start_date, end_date, balance_due, avatar, google_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    u_id, name, email, phone, role, 'Google Sign-In',
                    'Monthly Package', 12000, 20, 0, 20,
                    start_str, end_str, 12000, avatar, google_id
                ))
                conn.commit()

                new_user = {
                    "id": u_id,
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "role": role,
                    "org": "Google Sign-In",
                    "avatar": avatar,
                    "package": {
                        "name": "Monthly Package",
                        "cost": 12000,
                        "totalHours": 20,
                        "usedHours": 0,
                        "remainingHours": 20,
                        "startDate": start_str,
                        "endDate": end_str
                    },
                    "payments": [],
                    "balanceDue": 12000
                }

                sync_user_to_google_sheet(new_user, event_type="google_signup")
                conn.close()
                self.send_json({"success": True, "user": new_user, "isNew": True, "message": f"Google account created for {name}"})
                return

        # 16. Save Google Client ID Settings
        elif parsed.path == '/api/settings/google-auth':
            client_id = payload.get('googleClientId', '').strip()
            c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES ("googleClientId", ?)', (client_id,))
            conn.commit()
            conn.close()
            self.send_json({"success": True, "googleClientId": client_id, "message": "Google Client ID saved in SQLite database"})
            return

        conn.close()
        self.send_json({"error": "Endpoint not found"}, 404)

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

def run():
    init_db()
    print(f"[*] Initialized SQLite database: {DB_PATH}")
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    server = ThreadedHTTPServer(("0.0.0.0", PORT), ThinkStudioHandler)
    print(f"[*] Think Studio Server with SQLite Database running at http://localhost:{PORT}")
    server.serve_forever()

if __name__ == '__main__':
    run()
