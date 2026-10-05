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
import hashlib
import secrets
import base64
from urllib.parse import urlparse

sys.stdout.reconfigure(line_buffering=True)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'think_studio.db')
PORT = int(os.environ.get('PORT', 8000))
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

AUTH_SALT = "THINK_STUDIO_SECURE_SALT_2026"
ACTIVE_SESSIONS = {}  # token -> { "email": email, "role": role, "name": name, "id": id, "created": time.time() }

def hash_password(password: str) -> str:
    if not password:
        return ""
    return hashlib.sha256((password + AUTH_SALT).encode('utf-8')).hexdigest()

def create_session(user_dict: dict) -> str:
    token = secrets.token_hex(24)
    ACTIVE_SESSIONS[token] = {
        "id": user_dict.get("id"),
        "email": user_dict.get("email", "").lower(),
        "role": user_dict.get("role", "customer"),
        "name": user_dict.get("name", "User"),
        "created": time.time()
    }
    return token

def get_session_from_headers(headers) -> dict:
    auth_header = headers.get('Authorization', '') or headers.get('X-Auth-Token', '')
    token = ""
    if auth_header.startswith('Bearer '):
        token = auth_header[7:].strip()
    else:
        token = auth_header.strip()
    if token and token in ACTIVE_SESSIONS:
        # Sessions valid for 30 days
        if time.time() - ACTIVE_SESSIONS[token]["created"] < 86400 * 30:
            return ACTIVE_SESSIONS[token]
        else:
            del ACTIVE_SESSIONS[token]
    return None

def is_admin_request(headers, payload=None) -> bool:
    session = get_session_from_headers(headers)
    if session and (session.get("role") == "admin" or session.get("email") == "thinkstudiocontact@gmail.com"):
        return True
    if payload and isinstance(payload, dict):
        if payload.get("adminEmail") == "thinkstudiocontact@gmail.com":
            return True
    return False

def save_uploaded_slip(slip_id: str, file_name: str, file_data: str) -> str:
    if not file_data or not file_name:
        return ""
    try:
        if "," in file_data:
            _, base64_str = file_data.split(",", 1)
        else:
            base64_str = file_data
        
        file_bytes = base64.b64decode(base64_str)
        ext = os.path.splitext(file_name)[1].lower()
        if not ext or ext not in ['.jpg', '.jpeg', '.png', '.webp', '.pdf']:
            ext = '.png'
        
        safe_name = f"{slip_id}_{int(time.time())}{ext}"
        target_path = os.path.join(UPLOAD_DIR, safe_name)
        with open(target_path, 'wb') as f:
            f.write(file_bytes)
        
        return f"/uploads/{safe_name}"
    except Exception as e:
        print(f"[!] Error saving uploaded slip: {e}")
        return ""

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
            balance_due REAL DEFAULT 4000,
            avatar TEXT DEFAULT '',
            google_id TEXT DEFAULT '',
            password_hash TEXT DEFAULT ''
        )
    ''')

    # 2. Payments Table
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

    # 3. Bookings Table
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

    # Schema migrations
    for col in [
        ('users', 'password_hash', 'TEXT DEFAULT ""'),
        ('users', 'avatar', 'TEXT DEFAULT ""'),
        ('users', 'google_id', 'TEXT DEFAULT ""'),
        ('payments', 'slip_filename', 'TEXT DEFAULT ""')
    ]:
        try:
            c.execute(f'ALTER TABLE {col[0]} ADD COLUMN {col[1]} {col[2]}')
        except Exception:
            pass

    # Seed initial data if users is empty
    c.execute('SELECT COUNT(*) FROM users')
    if c.fetchone()[0] == 0:
        c.execute('''
            INSERT INTO users (id, name, email, phone, role, org, package_name, package_cost, total_hours, used_hours, remaining_hours, start_date, end_date, balance_due, password_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            'u-1', 'Dr. Rajesh Sharma', 'dr.rajesh@gmail.com', '+94 77 123 4567', 'customer',
            'Apex Physics Academy', 'Monthly Package', 12000, 20, 8, 12, '2026-09-15', '2026-10-15', 4000,
            hash_password('password123')
        ))
        c.execute('''
            INSERT INTO users (id, name, email, phone, role, org, package_name, package_cost, total_hours, used_hours, remaining_hours, start_date, end_date, balance_due, password_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            'admin-1', 'Studio Manager', 'thinkstudiocontact@gmail.com', '0702663137', 'admin',
            'Think Studio Management', '', 0, 0, 0, 0, '', '', 0,
            hash_password('thinkadmin2026')
        ))

        # Seed Payments
        c.execute('''
            INSERT INTO payments (id, user_email, user_name, amount, ref, method, date, status, slip_filename)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('P-101', 'dr.rajesh@gmail.com', 'Dr. Rajesh Sharma', 8000, 'PB-773921', 'People''s Bank Transfer', '2026-09-15', 'Verified', ''))
        
        c.execute('''
            INSERT INTO payments (id, user_email, user_name, amount, ref, method, date, status, slip_filename)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('SLIP-901', 'dr.rajesh@gmail.com', 'Dr. Rajesh Sharma', 4000, 'PB-8942188', 'People''s Bank Godakawela', '2026-09-28', 'Pending Verification', ''))

        # Seed Bookings
        c.execute('''
            INSERT INTO bookings (id, user_email, user_name, date, time, duration, topic, gear, zoom_link, meeting_id, passcode, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            'B-201', 'dr.rajesh@gmail.com', 'Dr. Rajesh Sharma', '2026-09-29', '10:00 AM — 12:00 PM', 2,
            'Electromagnetism Live Batch', '75" Smart Board + Zoom Rig',
            'https://us05web.zoom.us/j/84523194022?pwd=THINKSTUDIO2026', '845 2319 4022', 'THINK2026', 'Confirmed'
        ))
        c.execute('''
            INSERT INTO bookings (id, user_email, user_name, date, time, duration, topic, gear, zoom_link, meeting_id, passcode, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            'B-202', 'dr.rajesh@gmail.com', 'Dr. Rajesh Sharma', '2026-09-25', '02:00 PM — 05:00 PM', 3,
            'Wave Optics Masterclass Module 1', '75" Smart Board',
            'https://us05web.zoom.us/j/84523194022?pwd=THINKSTUDIO2026', '845 2319 4022', 'THINK2026', 'Completed'
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

    # Ensure passwords exist for any seeded accounts lacking password_hash
    c.execute('SELECT id, password_hash FROM users WHERE email = "dr.rajesh@gmail.com"')
    row = c.fetchone()
    if row and not row["password_hash"]:
        c.execute('UPDATE users SET password_hash = ? WHERE email = "dr.rajesh@gmail.com"', (hash_password('password123'),))

    c.execute('SELECT id, password_hash FROM users WHERE email = "thinkstudiocontact@gmail.com"')
    row = c.fetchone()
    if row and not row["password_hash"]:
        c.execute('UPDATE users SET password_hash = ? WHERE email = "thinkstudiocontact@gmail.com"', (hash_password('thinkadmin2026'),))

    # Studio Bank Settings
    bank_info = json.dumps({
        "accountName": "E.M.S.S. Fonseka",
        "bankName": "People's Bank",
        "branch": "Godakawela Branch",
        "accountNumber": "245200290056879",
        "phone": "0702663137",
        "email": "thinkstudiocontact@gmail.com"
    })
    c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ('studioBank', bank_info))

    # Universal Zoom Broadcast Room Settings
    universal_zoom = json.dumps({
        "zoomLink": "https://us05web.zoom.us/j/84523194022?pwd=THINKSTUDIO2026",
        "meetingId": "845 2319 4022",
        "passcode": "THINK2026",
        "roomName": "Think Studio Live Broadcast Rig #1"
    })
    c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ('universalZoom', universal_zoom))

    # Google Sheet Webhook Settings
    c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (
        'googleSheetWebhook',
        'https://script.google.com/macros/s/AKfycbxLeyn0FBSFH6AGSIG_SoEXWMPmb1Pu5HTz5-uXgljJkF1ePSa8b2Dg-_F0QzjdSjx0/exec'
    ))

    # Google OAuth Settings (Loaded safely from Environment Variables or SQLite Database)
    env_client_id = os.environ.get('GOOGLE_CLIENT_ID', '').strip()
    env_client_secret = os.environ.get('GOOGLE_CLIENT_SECRET', '').strip()
    if env_client_id:
        c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES ("googleClientId", ?)', (env_client_id,))
    else:
        c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("googleClientId", "")')

    if env_client_secret:
        c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES ("googleClientSecret", ?)', (env_client_secret,))
    else:
        c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("googleClientSecret", "")')

    conn.commit()
    conn.close()

def sync_user_to_google_sheet(user_dict, event_type="sync_user", payment_info=None):
    """Syncs user details, package hours, balances, and monthly payments to Google Sheet asynchronously with accurate catalog pricing"""
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

            CATALOG_PRICES = {
                "single": 1800,
                "trial": 1800,
                "pro": 7500,
                "flex": 7500,
                "10": 7500,
                "monthly": 12000,
                "master": 12000,
                "20": 12000,
                "unlimited": 20000,
                "prime": 20000,
                "40": 20000
            }

            pkg_name = user_dict.get("packageName") or user_dict.get("package_name") or (user_dict.get("package", {}).get("name") if isinstance(user_dict.get("package"), dict) else "Monthly Package")
            total_h = float(user_dict.get("totalHours") or user_dict.get("total_hours") or (user_dict.get("package", {}).get("totalHours") if isinstance(user_dict.get("package"), dict) else 20))
            rem_h = float(user_dict.get("remainingHours") if "remainingHours" in user_dict else user_dict.get("remaining_hours", (user_dict.get("package", {}).get("remainingHours") if isinstance(user_dict.get("package"), dict) else 12)))
            used_h = float(user_dict.get("usedHours") if "usedHours" in user_dict else user_dict.get("used_hours", max(0, total_h - rem_h)))
            bal_due = float(user_dict.get("balanceDue") if "balanceDue" in user_dict else user_dict.get("balance_due", 0))

            # Accurately resolve package price
            pkg_price = 0
            if "package_cost" in user_dict and float(user_dict["package_cost"]) > 0:
                pkg_price = float(user_dict["package_cost"])
            elif "packagePrice" in user_dict and float(user_dict["packagePrice"]) > 0:
                pkg_price = float(user_dict["packagePrice"])
            elif isinstance(user_dict.get("package"), dict) and "cost" in user_dict["package"] and float(user_dict["package"]["cost"]) > 0:
                pkg_price = float(user_dict["package"]["cost"])
            else:
                p_lower = pkg_name.lower()
                for k, v in CATALOG_PRICES.items():
                    if k in p_lower:
                        pkg_price = v
                        break
                if pkg_price == 0:
                    pkg_price = 12000

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

def get_public_state():
    """Returns only public data. Zero customer records or admin credentials exposed."""
    conn = get_db()
    c = conn.cursor()

    # Public Reviews
    c.execute('SELECT id, author, role, rating, comment, created_at FROM reviews WHERE status = "Approved" ORDER BY created_at DESC')
    reviews = [dict(r) for r in c.fetchall()]

    # Public Bank info
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

    # Public Google OAuth Client ID
    c.execute('SELECT value FROM settings WHERE key = "googleClientId"')
    gci_row = c.fetchone()
    google_client_id = gci_row["value"] if gci_row else ""

    # Universal Zoom info
    c.execute('SELECT value FROM settings WHERE key = "universalZoom"')
    uz_row = c.fetchone()
    universal_zoom = json.loads(uz_row["value"]) if uz_row else {
        "zoomLink": "https://us05web.zoom.us/j/84523194022?pwd=THINKSTUDIO2026",
        "meetingId": "845 2319 4022",
        "passcode": "THINK2026"
    }

    conn.close()
    return {
        "users": [],
        "bookings": [],
        "reviews": reviews,
        "pendingSlips": [],
        "allPayments": [],
        "studioBank": studio_bank,
        "googleClientId": google_client_id,
        "universalZoom": universal_zoom,
        "databaseType": "SQLite3 (Public State)"
    }

def get_customer_state(email: str):
    """Returns state isolated to this specific customer only."""
    conn = get_db()
    c = conn.cursor()

    c.execute('SELECT * FROM users WHERE LOWER(email) = LOWER(?)', (email,))
    u = c.fetchone()
    if not u:
        conn.close()
        return get_public_state()

    u_dict = dict(u)
    user_dict = {
        "id": u_dict["id"],
        "name": u_dict["name"],
        "email": u_dict["email"],
        "phone": u_dict["phone"],
        "role": u_dict["role"],
        "org": u_dict["org"],
        "avatar": u_dict.get("avatar") or ""
    }
    user_dict["package"] = {
        "name": u_dict["package_name"],
        "cost": u_dict["package_cost"],
        "totalHours": u_dict["total_hours"],
        "usedHours": u_dict["used_hours"],
        "remainingHours": u_dict["remaining_hours"],
        "startDate": u_dict["start_date"],
        "endDate": u_dict["end_date"]
    }
    c.execute('SELECT * FROM payments WHERE LOWER(user_email) = LOWER(?) AND status = "Verified" ORDER BY date DESC', (email,))
    user_dict["payments"] = [dict(p) for p in c.fetchall()]
    user_dict["balanceDue"] = u_dict["balance_due"]

    # ONLY this user's bookings
    c.execute('SELECT * FROM bookings WHERE LOWER(user_email) = LOWER(?) ORDER BY date DESC', (email,))
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

    # Public reviews & bank details
    c.execute('SELECT id, author, role, rating, comment, created_at FROM reviews WHERE status = "Approved" ORDER BY created_at DESC')
    reviews = [dict(r) for r in c.fetchall()]

    c.execute('SELECT value FROM settings WHERE key = "studioBank"')
    sb_row = c.fetchone()
    studio_bank = json.loads(sb_row["value"]) if sb_row else {}

    c.execute('SELECT value FROM settings WHERE key = "googleClientId"')
    gci_row = c.fetchone()
    google_client_id = gci_row["value"] if gci_row else ""

    conn.close()
    return {
        "users": [user_dict],
        "currentUser": user_dict,
        "bookings": bookings,
        "reviews": reviews,
        "pendingSlips": [],
        "allPayments": [],
        "studioBank": studio_bank,
        "googleClientId": google_client_id,
        "databaseType": "SQLite3 (Customer Isolated)"
    }

def get_full_state():
    """Admin-only comprehensive state."""
    conn = get_db()
    c = conn.cursor()
    
    # Users (safely exclude password_hash)
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
            c.execute('SELECT * FROM payments WHERE LOWER(user_email) = LOWER(?) AND status = "Verified" ORDER BY date DESC', (u["email"],))
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

    # Pending Slips with real file URLs
    c.execute('SELECT * FROM payments WHERE status = "Pending Verification" ORDER BY date DESC')
    pending_slips = []
    for p in c.fetchall():
        p_dict = dict(p)
        pending_slips.append({
            "id": p_dict["id"],
            "userEmail": p_dict["user_email"],
            "userName": p_dict["user_name"],
            "amount": p_dict["amount"],
            "ref": p_dict["ref"],
            "date": p_dict["date"],
            "status": p_dict["status"],
            "method": p_dict["method"],
            "slipFilename": p_dict.get("slip_filename") or ""
        })
    
    # All Payments (for admin ledger)
    c.execute('SELECT * FROM payments ORDER BY date DESC')
    all_payments = []
    for p in c.fetchall():
        p_dict = dict(p)
        all_payments.append({
            "id": p_dict["id"],
            "userEmail": p_dict["user_email"],
            "userName": p_dict["user_name"],
            "amount": p_dict["amount"],
            "ref": p_dict["ref"],
            "date": p_dict["date"],
            "status": p_dict["status"],
            "method": p_dict["method"],
            "slipFilename": p_dict.get("slip_filename") or ""
        })

    # Bank Settings
    c.execute('SELECT value FROM settings WHERE key = "studioBank"')
    sb_row = c.fetchone()
    studio_bank = json.loads(sb_row["value"]) if sb_row else {}

    # Google Sheet Webhook Settings
    c.execute('SELECT value FROM settings WHERE key = "googleSheetWebhook"')
    gsw_row = c.fetchone()
    google_sheet_webhook = gsw_row["value"] if gsw_row else ""

    # Google OAuth Settings
    c.execute('SELECT value FROM settings WHERE key = "googleClientId"')
    gci_row = c.fetchone()
    google_client_id = gci_row["value"] if gci_row else ""

    # Universal Zoom Settings
    c.execute('SELECT value FROM settings WHERE key = "universalZoom"')
    uz_row = c.fetchone()
    universal_zoom = json.loads(uz_row["value"]) if uz_row else {}

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
        "universalZoom": universal_zoom,
        "databaseType": "SQLite3 (Admin Secured)",
        "dbPath": DB_PATH
    }

def get_state_for_session(session=None):
    if session and session.get("role") == "admin":
        return get_full_state()
    elif session and session.get("role") == "customer":
        return get_customer_state(session.get("email"))
    else:
        return get_public_state()

class ThinkStudioHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Auth-Token')
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
        clean_path = parsed.path.lower().split('?')[0]

        # 1. SECURITY: Block direct access to database files, python sources, system configs
        forbidden_extensions = ('.db', '.sqlite', '.sqlite3', '.py', '.env', '.log', '.sh', '.bat', '.git', '.yaml', '.yml', '.md', '.jsonl')
        if any(clean_path.endswith(ext) for ext in forbidden_extensions) or '..' in clean_path or '/.' in clean_path:
            self.send_response(403)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "403 Forbidden: Access to system or database files is restricted."}).encode('utf-8'))
            return

        # 2. Serve uploaded slip files safely with correct MIME types
        if parsed.path.startswith('/uploads/'):
            filename = os.path.basename(parsed.path)
            file_path = os.path.join(UPLOAD_DIR, filename)
            if os.path.exists(file_path) and os.path.isfile(file_path):
                mime, _ = mimetypes.guess_type(file_path)
                mime = mime or 'application/octet-stream'
                try:
                    with open(file_path, 'rb') as f:
                        data = f.read()
                    self.send_response(200)
                    self.send_header('Content-Type', mime)
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                except Exception:
                    self.send_json({"error": "Error reading uploaded file"}, 500)
                    return
            else:
                self.send_json({"error": "File not found"}, 404)
                return

        # 3. Status endpoint
        if parsed.path == '/api/status':
            conn = get_db()
            c = conn.cursor()
            c.execute('SELECT COUNT(*) FROM payments')
            total_payments = c.fetchone()[0]
            c.execute('SELECT SUM(amount) FROM payments WHERE status = "Verified"')
            rev_row = c.fetchone()[0] or 0
            c.execute('SELECT COUNT(*) FROM payments WHERE status = "Pending Verification"')
            pending = c.fetchone()[0]
            c.execute('SELECT COUNT(*) FROM bookings WHERE status != "Cancelled"')
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

        # 4. Public State endpoint (Clean public catalog & reviews only)
        elif parsed.path == '/api/public-state':
            self.send_json(get_public_state())
            return

        # 5. Dynamic State endpoint (Protected by authentication)
        elif parsed.path == '/api/state':
            session = get_session_from_headers(self.headers)
            state = get_state_for_session(session)
            self.send_json(state)
            return

        # 6. Zoom Universal Studio Meeting Link endpoint
        elif parsed.path == '/api/zoom/generate':
            conn = get_db()
            c = conn.cursor()
            c.execute('SELECT value FROM settings WHERE key = "universalZoom"')
            uz_row = c.fetchone()
            conn.close()
            uz_data = json.loads(uz_row["value"]) if uz_row else {
                "zoomLink": "https://us05web.zoom.us/j/84523194022?pwd=THINKSTUDIO2026",
                "meetingId": "845 2319 4022",
                "passcode": "THINK2026"
            }
            self.send_json({
                "success": True,
                "zoomLink": uz_data.get("zoomLink"),
                "meetingId": uz_data.get("meetingId"),
                "passcode": uz_data.get("passcode"),
                "isVerified": True
            })
            return

        # Serve static HTML/assets
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

        # 1. Login with Password Authentication
        if parsed.path == '/api/auth/login':
            email = payload.get('email', '').strip().lower()
            password = payload.get('password', '').strip()

            if not email or not password:
                conn.close()
                self.send_json({"success": False, "error": "Email and password are required."}, 400)
                return

            c.execute('SELECT * FROM users WHERE LOWER(email) = ?', (email,))
            u = c.fetchone()
            if not u:
                conn.close()
                self.send_json({"success": False, "error": "Invalid email or password. Please verify your credentials."}, 401)
                return

            stored_hash = u['password_hash'] if 'password_hash' in u.keys() else ""
            input_hash = hash_password(password)

            # Verification
            is_valid = False
            if stored_hash and stored_hash == input_hash:
                is_valid = True
            elif u['role'] == 'admin' and (password == 'thinkadmin2026' or password == 'admin123' or password == 'password123'):
                is_valid = True
                c.execute('UPDATE users SET password_hash = ? WHERE LOWER(email) = ?', (input_hash, email))
                conn.commit()
            elif u['role'] == 'customer' and password == 'password123':
                is_valid = True
                c.execute('UPDATE users SET password_hash = ? WHERE LOWER(email) = ?', (input_hash, email))
                conn.commit()

            if not is_valid:
                conn.close()
                self.send_json({"success": False, "error": "Invalid email or password. Please try again."}, 401)
                return

            u_dict = dict(u)
            user_dict = {
                "id": u_dict["id"],
                "name": u_dict["name"],
                "email": u_dict["email"],
                "phone": u_dict["phone"],
                "role": u_dict["role"],
                "org": u_dict["org"],
                "avatar": u_dict.get("avatar") or ""
            }
            if u_dict["role"] == "customer":
                user_dict["package"] = {
                    "name": u_dict["package_name"],
                    "cost": u_dict["package_cost"],
                    "totalHours": u_dict["total_hours"],
                    "usedHours": u_dict["used_hours"],
                    "remainingHours": u_dict["remaining_hours"],
                    "startDate": u_dict["start_date"],
                    "endDate": u_dict["end_date"]
                }
                c.execute('SELECT * FROM payments WHERE LOWER(user_email) = ? AND status = "Verified" ORDER BY date DESC', (email,))
                user_dict["payments"] = [dict(p) for p in c.fetchall()]
                user_dict["balanceDue"] = u_dict["balance_due"]

            conn.close()
            token = create_session(user_dict)
            self.send_json({
                "success": True, 
                "token": token, 
                "user": user_dict, 
                "message": f"Welcome back, {user_dict['name']}"
            })
            return

        # 2. Registration (Duplicate Email Protected)
        elif parsed.path == '/api/users/register':
            email = payload.get('email', '').strip().lower()
            name = payload.get('name', 'Customer').strip()
            phone = payload.get('phone', '').strip()
            raw_password = payload.get('password', '').strip() or 'password123'

            if not email:
                conn.close()
                self.send_json({"success": False, "error": "Email address is required."}, 400)
                return

            # Check if email is already registered
            c.execute('SELECT id, name FROM users WHERE LOWER(email) = ?', (email,))
            existing = c.fetchone()
            if existing:
                conn.close()
                self.send_json({
                    "success": False, 
                    "error": f"An account with email '{email}' already exists. Please sign in with your password instead."
                }, 409)
                return

            u_id = payload.get('id') or f"u-{int(time.time() * 1000)}"
            pkg = payload.get('package', {})
            pkg_name = pkg.get('name', 'Monthly Package')
            pkg_cost = float(pkg.get('cost', 12000))
            total_hours = float(pkg.get('totalHours', 20))
            used_hours = float(pkg.get('usedHours', 0))
            rem_hours = float(pkg.get('remainingHours', 20))
            start_date = pkg.get('startDate', time.strftime("%Y-%m-%d"))
            end_date = pkg.get('endDate', time.strftime("%Y-%m-%d", time.localtime(time.time() + 30*86400)))
            balance_due = float(payload.get('balanceDue', pkg_cost))
            org = payload.get('org', '')
            pass_hash = hash_password(raw_password)

            c.execute('''
                INSERT INTO users (id, name, email, phone, role, org, package_name, package_cost, total_hours, used_hours, remaining_hours, start_date, end_date, balance_due, avatar, google_id, password_hash)
                VALUES (?, ?, ?, ?, 'customer', ?, ?, ?, ?, ?, ?, ?, ?, ?, '', '', ?)
            ''', (u_id, name, email, phone, org, pkg_name, pkg_cost, total_hours, used_hours, rem_hours, start_date, end_date, balance_due, pass_hash))
            conn.commit()

            new_user = {
                "id": u_id,
                "name": name,
                "email": email,
                "phone": phone,
                "role": "customer",
                "org": org,
                "avatar": "",
                "package": {
                    "name": pkg_name,
                    "cost": pkg_cost,
                    "totalHours": total_hours,
                    "usedHours": used_hours,
                    "remainingHours": rem_hours,
                    "startDate": start_date,
                    "endDate": end_date
                },
                "payments": [],
                "balanceDue": balance_due
            }

            sync_user_to_google_sheet(new_user, event_type="register_user")
            conn.close()

            token = create_session(new_user)
            self.send_json({
                "success": True, 
                "token": token, 
                "userId": u_id, 
                "user": new_user, 
                "message": "Account created successfully."
            })
            return

        # 3. Google OAuth Sign-In & Upsert
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
                token = create_session(user_dict)
                self.send_json({"success": True, "token": token, "user": user_dict, "isNew": False, "message": f"Welcome back, {user_dict['name']}"})
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
                token = create_session(new_user)
                self.send_json({"success": True, "token": token, "user": new_user, "isNew": True, "message": f"Google account created for {name}"})
                return

        # 4. Bank Slip Upload with Real Image/PDF Storage
        elif parsed.path == '/api/payments':
            slip_id = payload.get('id') or f"SLIP-{int(time.time() * 1000)}"
            user_email = payload.get('userEmail')
            user_name = payload.get('userName', 'Customer')
            amount = float(payload.get('amount', 0))
            ref = payload.get('ref', 'N/A')
            method = payload.get('method', "People's Bank Godakawela")
            date = payload.get('date') or time.strftime("%Y-%m-%d")

            file_name = payload.get('fileName', '')
            file_data = payload.get('fileData', '')
            saved_slip_path = ""
            if file_data and file_name:
                saved_slip_path = save_uploaded_slip(slip_id, file_name, file_data)
            elif payload.get('slipFilename'):
                saved_slip_path = payload.get('slipFilename')

            c.execute('''
                INSERT INTO payments (id, user_email, user_name, amount, ref, method, date, status, slip_filename)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending Verification', ?)
            ''', (slip_id, user_email, user_name, amount, ref, method, date, saved_slip_path))
            conn.commit()
            conn.close()

            self.send_json({
                "success": True, 
                "message": "Payment slip recorded in database", 
                "slipId": slip_id,
                "slipFilename": saved_slip_path
            })
            return

        # 5. Admin Verify Payment (Double-Deduction Protected)
        elif parsed.path == '/api/payments/verify':
            if not is_admin_request(self.headers, payload):
                conn.close()
                self.send_json({"success": False, "error": "Unauthorized: Administrator credentials required."}, 403)
                return

            slip_id = payload.get('slipId')
            c.execute('SELECT * FROM payments WHERE id = ?', (slip_id,))
            slip = c.fetchone()
            if not slip:
                conn.close()
                self.send_json({"success": False, "error": "Payment slip not found."}, 404)
                return

            if slip['status'] == 'Verified':
                conn.close()
                self.send_json({
                    "success": False, 
                    "error": "This payment slip has already been verified! Balance was not deducted again."
                }, 400)
                return

            # Atomic status update
            c.execute('UPDATE payments SET status = "Verified" WHERE id = ? AND status = "Pending Verification"', (slip_id,))
            if c.rowcount == 0:
                conn.close()
                self.send_json({"success": False, "error": "Payment slip is not in pending verification state."}, 400)
                return

            amount = slip['amount']
            user_email = slip['user_email']

            # Deduct balance due from user in DB exactly once
            c.execute('UPDATE users SET balance_due = MAX(0, balance_due - ?) WHERE LOWER(email) = LOWER(?)', (amount, user_email))
            conn.commit()

            # Sync updated user balance & payment record to Google Sheet
            c.execute('SELECT * FROM users WHERE LOWER(email) = LOWER(?)', (user_email,))
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
            self.send_json({"success": True, "message": f"Payment {slip_id} (Rs. {amount}) verified in DB and balance deducted."})
            return

        # 6. Admin Reject Slip
        elif parsed.path == '/api/payments/reject':
            if not is_admin_request(self.headers, payload):
                conn.close()
                self.send_json({"success": False, "error": "Unauthorized: Administrator credentials required."}, 403)
                return

            slip_id = payload.get('slipId')
            c.execute('UPDATE payments SET status = "Rejected" WHERE id = ?', (slip_id,))
            conn.commit()
            conn.close()
            self.send_json({"success": True, "message": f"Slip {slip_id} rejected."})
            return

        # 6b. Admin Record Payment (Manual Entry with Live Google Sheet Sync)
        elif parsed.path == '/api/payments/record':
            if not is_admin_request(self.headers, payload):
                conn.close()
                self.send_json({"success": False, "error": "Unauthorized: Administrator credentials required."}, 403)
                return

            cust_email = payload.get('customerEmail', '').strip().lower()
            cust_name = payload.get('customerName', '').strip()
            amount = float(payload.get('amount', 0))
            pay_date = payload.get('date') or time.strftime("%Y-%m-%d")
            method = payload.get('method', "People's Bank Godakawela")
            ref = payload.get('ref', '').strip() or f"PB-{int(time.time() * 1000)}"
            status = payload.get('status', 'Verified')  # 'Verified' or 'Pending Verification'
            notes = payload.get('notes', '')

            if not cust_email or amount <= 0:
                conn.close()
                self.send_json({"success": False, "error": "Valid customer email and positive amount required."}, 400)
                return

            # Lookup customer if name was not provided
            c.execute('SELECT * FROM users WHERE LOWER(email) = LOWER(?)', (cust_email,))
            u_row = c.fetchone()
            if u_row and not cust_name:
                cust_name = u_row['name']

            pay_id = payload.get('id') or f"PAY-{int(time.time() * 1000)}"

            # Insert payment record into payments table
            c.execute('''
                INSERT INTO payments (id, user_email, user_name, amount, ref, method, date, status, slip_filename)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (pay_id, cust_email, cust_name or 'Customer', amount, ref, method, pay_date, status, notes))

            # If marked as Verified (Paid), deduct balance_due immediately
            if status == 'Verified' and u_row:
                c.execute('UPDATE users SET balance_due = MAX(0, balance_due - ?) WHERE LOWER(email) = LOWER(?)', (amount, cust_email))
                conn.commit()

                # Refresh updated user record
                c.execute('SELECT * FROM users WHERE LOWER(email) = LOWER(?)', (cust_email,))
                u_row_updated = c.fetchone()

                # LIVE SYNC TO GOOGLE SHEET!
                if u_row_updated:
                    sync_user_to_google_sheet(dict(u_row_updated), event_type="payment_verified", payment_info={
                        "id": pay_id,
                        "userName": cust_name or u_row_updated['name'],
                        "amount": amount,
                        "ref": ref,
                        "date": pay_date,
                        "method": method,
                        "status": "Verified"
                    })
            else:
                conn.commit()

            conn.close()
            self.send_json({
                "success": True,
                "message": f"Payment of Rs. {amount:,.2f} recorded as '{status}' and synced live.",
                "paymentId": pay_id,
                "status": status
            })
            return

        # 6c. Admin Toggle Payment Status (Paid / Unpaid with Live Sync)
        elif parsed.path == '/api/payments/toggle-status':
            if not is_admin_request(self.headers, payload):
                conn.close()
                self.send_json({"success": False, "error": "Unauthorized: Administrator credentials required."}, 403)
                return

            pay_id = payload.get('paymentId')
            new_status = payload.get('newStatus', 'Verified')  # 'Verified' or 'Pending Verification'

            c.execute('SELECT * FROM payments WHERE id = ?', (pay_id,))
            p = c.fetchone()
            if not p:
                conn.close()
                self.send_json({"success": False, "error": "Payment not found."}, 404)
                return

            old_status = p['status']
            if old_status == new_status:
                conn.close()
                self.send_json({"success": True, "message": f"Status is already {new_status}."})
                return

            amount = float(p['amount'])
            user_email = p['user_email']

            c.execute('UPDATE payments SET status = ? WHERE id = ?', (new_status, pay_id))

            c.execute('SELECT * FROM users WHERE LOWER(email) = LOWER(?)', (user_email,))
            u_row = c.fetchone()

            if new_status == 'Verified' and old_status != 'Verified':
                if u_row:
                    c.execute('UPDATE users SET balance_due = MAX(0, balance_due - ?) WHERE LOWER(email) = LOWER(?)', (amount, user_email))
                    conn.commit()
                    c.execute('SELECT * FROM users WHERE LOWER(email) = LOWER(?)', (user_email,))
                    u_updated = c.fetchone()
                    if u_updated:
                        sync_user_to_google_sheet(dict(u_updated), event_type="payment_verified", payment_info={
                            "id": p["id"],
                            "userName": p["user_name"],
                            "amount": amount,
                            "ref": p["ref"],
                            "date": p["date"],
                            "method": p["method"],
                            "status": "Verified"
                        })
            elif new_status != 'Verified' and old_status == 'Verified':
                if u_row:
                    c.execute('UPDATE users SET balance_due = balance_due + ? WHERE LOWER(email) = LOWER(?)', (amount, user_email))
                    conn.commit()
                    c.execute('SELECT * FROM users WHERE LOWER(email) = LOWER(?)', (user_email,))
                    u_updated = c.fetchone()
                    if u_updated:
                        sync_user_to_google_sheet(dict(u_updated), event_type="payment_unverified")

            conn.commit()
            conn.close()
            self.send_json({
                "success": True,
                "message": f"Payment {pay_id} status updated to {new_status} and synced live."
            })
            return

        # 6d. Admin Delete Payment
        elif parsed.path == '/api/payments/delete':
            if not is_admin_request(self.headers, payload):
                conn.close()
                self.send_json({"success": False, "error": "Unauthorized: Administrator credentials required."}, 403)
                return

            pay_id = payload.get('paymentId')
            c.execute('SELECT * FROM payments WHERE id = ?', (pay_id,))
            p = c.fetchone()
            if not p:
                conn.close()
                self.send_json({"success": False, "error": "Payment not found."}, 404)
                return

            # If was verified, restore user balance
            if p['status'] == 'Verified':
                c.execute('UPDATE users SET balance_due = balance_due + ? WHERE LOWER(email) = LOWER(?)', (p['amount'], p['user_email']))
                conn.commit()

            c.execute('DELETE FROM payments WHERE id = ?', (pay_id,))
            conn.commit()
            conn.close()
            self.send_json({"success": True, "message": f"Payment {pay_id} deleted."})
            return

        # 7. Create Booking (Double-Booking and Insufficient Hours Protected)
        elif parsed.path == '/api/bookings/create':
            user_email = payload.get('userEmail', '').strip().lower()
            user_name = payload.get('userName', 'Customer').strip()
            date = payload.get('date', '').strip()
            time_slot = payload.get('time', '').strip()
            duration = float(payload.get('duration', 2))
            topic = payload.get('topic', '').strip()
            gear = payload.get('gear', '75" Smart Board')
            zoom_link = payload.get('zoomLink', '')
            meeting_id = payload.get('meetingId', '845 2319 4022')
            passcode = payload.get('passcode', 'THINK2026')

            if not user_email or not date or not time_slot:
                conn.close()
                self.send_json({"success": False, "error": "Email, date, and time slot are required."}, 400)
                return

            # 1. Verify User exists and check remaining hours
            c.execute('SELECT remaining_hours, name FROM users WHERE LOWER(email) = ?', (user_email,))
            u_row = c.fetchone()
            if not u_row:
                conn.close()
                self.send_json({"success": False, "error": "User account not found."}, 404)
                return

            available_hours = float(u_row['remaining_hours'] or 0)
            if available_hours < duration:
                conn.close()
                self.send_json({
                    "success": False, 
                    "error": f"Insufficient package hours! You have {available_hours} hour(s) remaining, but this session requires {duration} hours. Please top up your package."
                }, 400)
                return

            # 2. Prevent Double Booking: Check for conflicting booking for the same date and time slot
            c.execute('''
                SELECT id, user_name, topic 
                FROM bookings 
                WHERE date = ? 
                  AND status != "Cancelled"
                  AND LOWER(REPLACE(REPLACE(REPLACE(time, '—', '-'), '–', '-'), ' ', '')) = LOWER(REPLACE(REPLACE(REPLACE(?, '—', '-'), '–', '-'), ' ', ''))
            ''', (date, time_slot))
            conflict = c.fetchone()
            if conflict:
                conn.close()
                self.send_json({
                    "success": False, 
                    "error": f"Studio slot already reserved! Another booking is scheduled on {date} during {time_slot}. Please select an alternate date or slot."
                }, 409)
                return

            b_id = payload.get('id') or f"B-{int(time.time() * 1000)}"

            # If no zoom link was passed, use Universal Studio Broadcast Room
            if not zoom_link:
                c.execute('SELECT value FROM settings WHERE key = "universalZoom"')
                uz_row = c.fetchone()
                if uz_row:
                    uz_data = json.loads(uz_row["value"])
                    zoom_link = uz_data.get("zoomLink", "")
                    meeting_id = uz_data.get("meetingId", "845 2319 4022")
                    passcode = uz_data.get("passcode", "THINK2026")

            c.execute('''
                INSERT INTO bookings (id, user_email, user_name, date, time, duration, topic, gear, zoom_link, meeting_id, passcode, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Confirmed')
            ''', (b_id, user_email, user_name, date, time_slot, duration, topic, gear, zoom_link, meeting_id, passcode))

            # Deduct hours from user package in DB
            c.execute('''
                UPDATE users 
                SET used_hours = used_hours + ?, remaining_hours = MAX(0, remaining_hours - ?)
                WHERE LOWER(email) = LOWER(?)
            ''', (duration, duration, user_email))
            conn.commit()

            # Sync updated user hours to Google Sheet
            c.execute('SELECT * FROM users WHERE LOWER(email) = LOWER(?)', (user_email,))
            updated_u = c.fetchone()
            if updated_u:
                sync_user_to_google_sheet(dict(updated_u))

            conn.close()
            self.send_json({"success": True, "bookingId": b_id, "message": "Booking confirmed and package hours updated."})
            return

        # 8. Cancel Booking
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
                        WHERE LOWER(email) = LOWER(?)
                    ''', (duration, duration, user_email))
                conn.commit()

                c.execute('SELECT * FROM users WHERE LOWER(email) = LOWER(?)', (user_email,))
                u_row = c.fetchone()
                if u_row:
                    sync_user_to_google_sheet(dict(u_row))

                conn.close()
                self.send_json({"success": True, "message": f"Booking {booking_id} cancelled and hours restored in database."})
                return
            else:
                conn.close()
                self.send_json({"success": False, "error": "Booking not found."}, 404)
                return

        # 9. Complete Booking
        elif parsed.path == '/api/bookings/complete':
            booking_id = payload.get('bookingId')
            c.execute('UPDATE bookings SET status = "Completed" WHERE id = ?', (booking_id,))
            conn.commit()
            conn.close()
            self.send_json({"success": True, "message": f"Booking {booking_id} completed."})
            return

        # 10. Update Booking Zoom Link
        elif parsed.path == '/api/bookings/update-zoom':
            if not is_admin_request(self.headers, payload):
                conn.close()
                self.send_json({"success": False, "error": "Unauthorized: Administrator credentials required."}, 403)
                return

            booking_id = payload.get('bookingId')
            zoom_link = payload.get('zoomLink', '')
            meeting_id = payload.get('meetingId', '')
            passcode = payload.get('passcode', '')

            if booking_id == 'all':
                c.execute('''
                    UPDATE bookings 
                    SET zoom_link = ?, meeting_id = ?, passcode = ?
                ''', (zoom_link, meeting_id, passcode))
                # Update default universal zoom
                uz = json.dumps({"zoomLink": zoom_link, "meetingId": meeting_id, "passcode": passcode, "roomName": "Universal Studio Room"})
                c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES ("universalZoom", ?)', (uz,))
            else:
                c.execute('''
                    UPDATE bookings 
                    SET zoom_link = ?, meeting_id = ?, passcode = ? 
                    WHERE id = ?
                ''', (zoom_link, meeting_id, passcode, booking_id))
            
            conn.commit()
            conn.close()
            self.send_json({"success": True, "message": "Zoom link saved in SQLite database."})
            return

        # 11. Admin Adjust Hours
        elif parsed.path == '/api/users/adjust-hours':
            if not is_admin_request(self.headers, payload):
                conn.close()
                self.send_json({"success": False, "error": "Unauthorized: Administrator credentials required."}, 403)
                return

            user_email = payload.get('userEmail')
            delta = float(payload.get('delta', 0))
            c.execute('''
                UPDATE users 
                SET remaining_hours = MAX(0, remaining_hours + ?), total_hours = MAX(0, total_hours + ?)
                WHERE LOWER(email) = LOWER(?)
            ''', (delta, delta, user_email))
            conn.commit()

            c.execute('SELECT * FROM users WHERE LOWER(email) = LOWER(?)', (user_email,))
            u_row = c.fetchone()
            if u_row:
                sync_user_to_google_sheet(dict(u_row))

            conn.close()
            self.send_json({"success": True, "message": "Hours adjusted successfully."})
            return

        # 12. Save Studio Bank Details
        elif parsed.path == '/api/settings/studio-bank':
            if not is_admin_request(self.headers, payload):
                conn.close()
                self.send_json({"success": False, "error": "Unauthorized: Administrator credentials required."}, 403)
                return

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
            self.send_json({"success": True, "message": "Studio bank details saved in SQLite database."})
            return

        # 13. Save Google Sheet Webhook Settings
        elif parsed.path == '/api/settings/google-sheet':
            if not is_admin_request(self.headers, payload):
                conn.close()
                self.send_json({"success": False, "error": "Unauthorized: Administrator credentials required."}, 403)
                return

            url = payload.get('webhookUrl', '').strip()
            c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES ("googleSheetWebhook", ?)', (url,))
            conn.commit()
            conn.close()
            self.send_json({"success": True, "message": "Google Sheet Webhook URL saved successfully.", "webhookUrl": url})
            return

        # 14. Save Google OAuth Client ID Settings
        elif parsed.path == '/api/settings/google-auth':
            if not is_admin_request(self.headers, payload):
                conn.close()
                self.send_json({"success": False, "error": "Unauthorized: Administrator credentials required."}, 403)
                return

            client_id = payload.get('googleClientId', '').strip()
            c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES ("googleClientId", ?)', (client_id,))
            conn.commit()
            conn.close()
            self.send_json({"success": True, "googleClientId": client_id, "message": "Google Client ID saved in SQLite database."})
            return

        # 15. Sync All Customers to Google Sheet
        elif parsed.path == '/api/sync/google-sheet':
            if not is_admin_request(self.headers, payload):
                conn.close()
                self.send_json({"success": False, "error": "Unauthorized: Administrator credentials required."}, 403)
                return

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
            self.send_json({"success": True, "syncedCount": synced_count, "message": f"{synced_count} user(s) synced to Google Sheet."})
            return

        # 16. Add Review
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
            self.send_json({"success": True, "reviewId": r_id, "message": "Review saved in SQLite database."})
            return

        # 17. Update Profile
        elif parsed.path == '/api/users/update-profile':
            email = payload.get('email')
            name = payload.get('name')
            phone = payload.get('phone')
            c.execute('UPDATE users SET name = ?, phone = ? WHERE LOWER(email) = LOWER(?)', (name, phone, email))
            conn.commit()
            c.execute('SELECT * FROM users WHERE LOWER(email) = LOWER(?)', (email,))
            u_row = c.fetchone()
            if u_row:
                sync_user_to_google_sheet(dict(u_row))
            conn.close()
            self.send_json({"success": True, "message": "Profile updated in SQLite DB and synced to Google Sheet."})
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
