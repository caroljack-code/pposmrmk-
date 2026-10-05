#!/usr/bin/env python3
"""Diagnostic test: Verify Cloudinary DB upload/download works correctly"""
import sys
import os
import shutil
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['VERCEL'] = '1'  # Force serverless mode on
from backend.app import (
    IS_SERVERLESS,
    DB_NAME,
    BASE_DIR,
    CLOUDINARY_DB_PUBLIC_ID,
    save_db_to_cloudinary,
    restore_db_from_cloudinary,
    _cloudinary_db_url,
    get_db_connection,
    init_db,
)

def step(name):
    print(f"\n{'='*60}\n>>> {name}\n{'='*60}")

step("1. Environment Check")
print(f"IS_SERVERLESS: {IS_SERVERLESS}")
print(f"DB_NAME: {DB_NAME}")
print(f"BASE_DIR: {BASE_DIR}")
print(f"CLOUDINARY_DB_PUBLIC_ID: {CLOUDINARY_DB_PUBLIC_ID}")
print(f"Expected Cloudinary URL: {_cloudinary_db_url()}")

# Make sure /tmp pos.db exists for test
step("2. Ensure test DB exists with sample product")
if os.path.exists(DB_NAME):
    os.remove(DB_NAME)
# Seed from bundled if exists, else init fresh
orig = os.path.join(BASE_DIR, 'pos.db')
if os.path.exists(orig):
    shutil.copy2(orig, DB_NAME)
    print(f"Copied bundled pos.db -> {DB_NAME} ({os.path.getsize(DB_NAME)} bytes)")
else:
    init_db()
    print(f"Inited fresh DB -> {DB_NAME} ({os.path.getsize(DB_NAME)} bytes)")

conn = get_db_connection()
# Insert a test marker to verify later
try:
    conn.execute("INSERT INTO products (name, price, stock, category) VALUES (?, ?, ?, ?)",
                 ('__TEST_SYNC_PRODUCT__', 9999, 7, 'SyncTest'))
    conn.commit()
    print("Inserted sentinel product: __TEST_SYNC_PRODUCT__ (price=9999)")
except Exception as e:
    print(f"Insert note: {e}")
conn.close()

db_size_before = os.path.getsize(DB_NAME)
print(f"DB size before upload: {db_size_before} bytes")

step("3. Test: save_db_to_cloudinary()")
ok_save = save_db_to_cloudinary()
print(f"save_db_to_cloudinary() returned: {ok_save}")

step("4. Test: restore_db_from_cloudinary() - delete local DB first")
# Move current DB aside
backup = DB_NAME + ".bak"
if os.path.exists(backup): os.remove(backup)
shutil.move(DB_NAME, backup)
print(f"Moved {DB_NAME} -> {backup}")
print(f"Local DB exists now? {os.path.exists(DB_NAME)}")

# Force restore from Cloudinary
ok_restore = restore_db_from_cloudinary(force=True)
print(f"restore_db_from_cloudinary(force=True) returned: {ok_restore}")
print(f"Local DB exists after restore? {os.path.exists(DB_NAME)}")
if os.path.exists(DB_NAME):
    db_size_after = os.path.getsize(DB_NAME)
    print(f"Restored DB size: {db_size_after} bytes (before upload: {db_size_before})")
    # Verify sentinel
    conn2 = get_db_connection()
    row = conn2.execute("SELECT id, name, price, stock FROM products WHERE name=?",
                        ('__TEST_SYNC_PRODUCT__',)).fetchone()
    if row:
        print(f"✅ RESTORE VERIFIED: sentinel found! id={row['id']} name={row['name']} price={row['price']} stock={row['stock']}")
    else:
        print("❌ RESTORE FAILED: sentinel product missing.")
    conn2.close()
else:
    print("❌ RESTORE FAILED: DB file not present after restore.")

# Cleanup test
step("5. Cleanup")
if os.path.exists(backup):
    shutil.move(backup, DB_NAME)
    print(f"Restored original DB from backup")
# Delete sentinel product if present
conn3 = get_db_connection()
cur = conn3.cursor()
cur.execute("DELETE FROM products WHERE name='__TEST_SYNC_PRODUCT__'")
conn3.commit()
print(f"Deleted {cur.rowcount} test rows")
conn3.close()

step("6. Summary")
if ok_save and os.path.exists(DB_NAME):
    print("✅ Cloudinary DB sync: WORKING NORMALLY")
else:
    print("❌ Cloudinary DB sync: BROKEN")
sys.exit(0 if ok_save and os.path.exists(DB_NAME) else 1)
