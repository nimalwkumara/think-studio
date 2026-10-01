import re
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

with open('server.py', 'r', encoding='utf-8') as f:
    server = f.read()

print("========================================")
print("       THINK STUDIO DEEP AUDIT          ")
print("========================================")

# 1. API Endpoint Matching
fetch_urls = set(re.findall(r"fetch\(['\"](/api/[a-zA-Z0-9_\-/]+)['\"]", html))
server_paths = set(re.findall(r"parsed\.path\s*==\s*['\"](/api/[a-zA-Z0-9_\-/]+)['\"]", server))

print(f"\n1. API ENDPOINTS CHECK:")
print(f"   Frontend calls ({len(fetch_urls)}): {sorted(list(fetch_urls))}")
print(f"   Backend supports ({len(server_paths)}): {sorted(list(server_paths))}")
missing = fetch_urls - server_paths
if missing:
    print(f"   [BUG] Missing endpoints on backend: {missing}")
else:
    print("   [OK] All frontend fetch calls are supported by the backend!")

# 2. Check operations that mutate state locally but may NOT have backend API calls
print(f"\n2. DATA PERSISTENCE & MUTATION AUDIT:")
mutations = [
    ("Cancel booking (User)", r"function cancelBooking"),
    ("Admin cancel booking", r"function adminCancelBooking"),
    ("Admin complete booking", r"function markBookingCompleted"),
    ("Submit review", r"function handleSubmitReview"),
    ("Update profile", r"function handleUpdateProfile"),
    ("Update studio bank", r"function handleUpdateStudioBank"),
]

for name, pattern in mutations:
    m = re.search(pattern + r".*?(?=\n    function|\Z)", html, re.DOTALL)
    if m:
        code = m.group(0)
        has_fetch = "fetch(" in code
        has_save = "saveState(" in code
        print(f"   - {name}: LocalStorage={has_save}, Backend API Fetch={has_fetch}")

# 3. ID Audit
scripts = '\n'.join(re.findall(r'<script>(.*?)</script>', html, re.DOTALL))
called_ids = set(re.findall(r'document\.getElementById\([\'"]([a-zA-Z0-9_-]+)[\'"]\)', scripts))
defined_ids = set(re.findall(r'id=[\'"]([a-zA-Z0-9_-]+)[\'"]', html))
missing_ids = called_ids - defined_ids
print(f"\n3. DOM ID INTEGRITY AUDIT:")
if missing_ids:
    print(f"   [BUG] Missing IDs in HTML called by JS: {missing_ids}")
else:
    print(f"   [OK] All {len(called_ids)} DOM IDs referenced in JS exist in HTML.")

# 4. Check all form inputs inside modals / sections
print(f"\n4. FORM INPUT VALIDATIONS:")
inputs = re.findall(r'<input\s+([^>]+)>', html)
for inp in inputs:
    if 'id=' in inp and 'required' not in inp and 'type="hidden"' not in inp and 'checkbox' not in inp:
        # Check if it should be required or optional
        pass
print(f"   [INFO] Scanned {len(inputs)} form input elements.")

# 5. Check Bank details and Contact info consistency
print(f"\n5. OFFICIAL INFORMATION CONSISTENCY:")
phone_count = len(re.findall(r'0702663137', html))
email_count = len(re.findall(r'thinkstudiocontact@gmail\.com', html))
acc_count = len(re.findall(r'245200290056879', html))
fonseka_count = len(re.findall(r'E\.M\.S\.S\. Fonseka', html))
print(f"   - Phone (0702663137): {phone_count} occurrences")
print(f"   - Email (thinkstudiocontact@gmail.com): {email_count} occurrences")
print(f"   - Account (245200290056879): {acc_count} occurrences")
print(f"   - Account Name (E.M.S.S. Fonseka): {fonseka_count} occurrences")
