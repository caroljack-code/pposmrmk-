#!/usr/bin/env python3
"""
One-time bootstrap:
Push your local backend/pos.db to Cloudinary so Vercel can restore it.

Run this ON YOUR LOCAL COMPUTER (where pos.db has real products).
You only need to run this once — after that every write syncs automatically.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Force serverless mode so save_db_to_cloudinary actually runs uploads
os.environ['VERCEL'] = '1'

from backend.app import (
    BASE_DIR,
    IS_SERVERLESS,
    CLOUDINARY_DB_PUBLIC_ID,
    save_db_to_cloudinary,
    restore_db_from_cloudinary,
    get_db_connection,
    init_db,
    _cloudinary_db_url,
    _cloudinary_resource_info,
    _read_local_version,
    _write_local_version,
    DB_NAME,
)
import shutil

def main():
    print("=" * 70)
    print("BOOTSTRAP: Push local backend/pos.db to Cloudinary")
    print("=" * 70)
    print(f"IS_SERVERLESS mode (forced): {IS_SERVERLESS}")
    print(f"DB_NAME (target /tmp copy): {DB_NAME}")
    print(f"Cloudinary public_id:       {CLOUDINARY_DB_PUBLIC_ID}")
    print(f"Cloudinary URL:             {_cloudinary_db_url()}")

    bundled = os.path.join(BASE_DIR, "pos.db")
    if not os.path.exists(bundled):
        print(f"\n❌ ERROR: bundled DB not found at {bundled}")
        print("   Your local POS database (with real products) should be at:")
        print(f"   {bundled}")
        return 1
    print(f"\n✅ Found local DB: {bundled}")
    print(f"   Size: {os.path.getsize(bundled)} bytes")

    # Count rows before upload (for user info only)
    import sqlite3 as _sql
    src = _sql.connect(bundled)
    src.row_factory = _sql.Row
    for t in ['users', 'products', 'sales', 'sale_items']:
        try:
            n = src.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()['n']
            print(f"   Table '{t}': {n} rows")
        except Exception:
            pass
    src.close()

    # Copy to /tmp for the save function to pick it up
    print(f"\nCopying bundled -> /tmp/pos.db ...")
    shutil.copy2(bundled, DB_NAME)
    print(f"✅ /tmp/pos.db ready ({os.path.getsize(DB_NAME)} bytes)")

    print(f"\n📤 Uploading to Cloudinary...")
    ok = save_db_to_cloudinary()
    if not ok:
        print("❌ save_db_to_cloudinary() FAILED — check errors above")
        return 2
    print("✅ save_db_to_cloudinary() returned True")

    # Verify: does Cloudinary API now see it?
    info = _cloudinary_resource_info()
    if info:
        print(f"\n✅ Cloudinary resource info:")
        print(f"   version = {info.get('version')}")
        print(f"   bytes   = {info.get('bytes')}")
        print(f"   created = {info.get('created_at')}")
    else:
        print("\n❌ After save, Cloudinary reports no resource. Upload may have failed silently.")
        return 3

    # Verify: restore into a NEW filename and check row counts
    print(f"\n🧪 Verifying download & integrity (restore into test file)...")
    import tempfile, time
    tmpverify = DB_NAME + ".verify"
    if os.path.exists(tmpverify): os.remove(tmpverify)

    import requests
    info2 = _cloudinary_resource_info()
    ver = info2.get('version') if info2 else None
    url = _cloudinary_db_url(version=ver)
    r = requests.get(url, timeout=30)
    if r.status_code != 200 or len(r.content) < 1000:
        print(f"❌ Download failed: HTTP {r.status_code}, len={len(getattr(r,'content',b''))}")
        return 4
    with open(tmpverify, 'wb') as f:
        f.write(r.content)
    print(f"✅ Downloaded {len(r.content)} bytes to verify")

    conn = _sql.connect(tmpverify)
    conn.row_factory = _sql.Row
    print(f"\n✅ Downloaded DB row counts:")
    all_ok = True
    for t in ['users', 'products', 'sales', 'sale_items']:
        try:
            n = conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()['n']
            print(f"   Table '{t}': {n} rows")
        except Exception:
            all_ok = False
            print(f"   Table '{t}': MISSING")
    conn.close()
    try: os.remove(tmpverify)
    except Exception: pass

    if all_ok:
        print("\n" + "=" * 70)
        print("🎉 BOOTSTRAP SUCCESSFUL!")
        print("=" * 70)
        print("Your local database has been uploaded to Cloudinary.\n")
        print("On Vercel / the live site:")
        print("  1. Hard-refresh your browser (Ctrl+Shift+R / Cmd+Shift+R)")
        print("  2. Login as admin")
        print("  3. On first request, DB will be auto-restored from Cloudinary")
        print("  4. All future writes (products, sales, users, etc.) are auto-synced\n")
        print(f"Live DB URL (raw): {_cloudinary_db_url()}")
        return 0
    else:
        print("\n❌ Integrity check failed — tables missing after restore?")
        return 5

if __name__ == '__main__':
    sys.exit(main())
