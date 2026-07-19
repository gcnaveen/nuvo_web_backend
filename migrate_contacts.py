#!/usr/bin/env python3
"""
migrate_contacts.py — one-off importer for the admin "Database" (business
contacts) section, from an Excel export into MongoDB.

Target collections (must match apps/contacts/models.py exactly):
  - contacts            (Contact)          _id = uuid string
  - contact_categories  (ContactCategory)  _id = uuid string

SAFETY
------
* DRY-RUN by default: it connects and READS only (to detect duplicates),
  prints exactly what WOULD be inserted, and writes nothing.
* Pass --commit to actually insert.
* Duplicates are skipped: a contact is considered already present if a doc
  with the same full_name (case-insensitive) AND same digits-only
  contact_number_1 already exists in `contacts` (or appears earlier in the
  sheet itself).
* The 7 categories from column A are created in `contact_categories` only if
  a category of that name does not already exist.

Excel column mapping (by POSITION — header text is only sanity-checked):
  A Category           -> category
  B Name               -> full_name        (required)
  C Contact Number-1   -> contact_number_1 (required)
  D Contact Number-2   -> contact_number_2
  E Company            -> company_name
  F Email              -> email
  G designation        -> designation
  H Referred by        -> referred_by

USAGE
-----
  # dry run (default, no writes):
  python migrate_contacts.py --file "/path/Database from SIWPC - HYD.xlsx"

  # actually write to the DB:
  python migrate_contacts.py --file "/path/....xlsx" --commit

MONGO_URI is read from the backend .env (same file Django uses) unless
--mongo-uri is passed.
"""
import argparse
import os
import re
import sys
import uuid
from datetime import datetime

try:
    import openpyxl
    from pymongo import MongoClient
    from dotenv import load_dotenv
except ImportError as e:
    sys.exit(f"Missing dependency: {e}. Install with: pip install openpyxl pymongo python-dotenv")

HERE = os.path.dirname(os.path.abspath(__file__))

# Fixed column order in the sheet (0-indexed). Header text is checked but the
# position is what actually drives the mapping.
COLS = {
    "category":         0,
    "full_name":        1,
    "contact_number_1": 2,
    "contact_number_2": 3,
    "company_name":     4,
    "email":            5,
    "designation":      6,
    "referred_by":      7,
}
EXPECTED_HEADERS = [
    "category", "name", "contact number - 1", "contact number - 2",
    "company", "email", "designation", "referred by",
]


def norm(v):
    """Trim ends and collapse internal whitespace runs to a single space."""
    if v is None:
        return ""
    return re.sub(r"\s+", " ", str(v)).strip()


def digits(v):
    return re.sub(r"\D", "", v or "")


def dedup_key(full_name, contact1):
    return f"{full_name.strip().lower()}|{digits(contact1)}"


def load_rows(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.worksheets[0]
    all_rows = list(ws.iter_rows(values_only=True))
    if not all_rows:
        sys.exit("Sheet is empty.")

    header = [norm(h).lower() for h in all_rows[0]]
    # sanity check headers against expected (warn, don't hard-fail)
    for i, exp in enumerate(EXPECTED_HEADERS):
        got = header[i] if i < len(header) else ""
        if exp not in got and got not in exp:
            print(f"  ⚠ header col {chr(65+i)}: expected ~{exp!r}, got {got!r} "
                  f"(mapping is by position, continuing)")

    contacts = []
    skipped_empty = 0
    for raw in all_rows[1:]:
        # pad short rows
        raw = list(raw) + [None] * (8 - len(raw))
        rec = {field: norm(raw[idx]) for field, idx in COLS.items()}
        if not any(rec.values()):
            skipped_empty += 1
            continue
        contacts.append(rec)
    return contacts, skipped_empty


def main():
    ap = argparse.ArgumentParser(description="Import business contacts from Excel into MongoDB.")
    ap.add_argument("--file", required=True, help="Path to the .xlsx file")
    ap.add_argument("--commit", action="store_true",
                    help="Actually write to the DB. Without this it is a dry run.")
    ap.add_argument("--mongo-uri", default=None,
                    help="Override MONGO_URI (defaults to backend .env)")
    ap.add_argument("--db", default=None,
                    help="Database name. Required if the URI has no /<dbname> path (e.g. --db nuvohosting)")
    ap.add_argument("--env", default=os.path.join(HERE, ".env"),
                    help="Path to .env holding MONGO_URI")
    args = ap.parse_args()

    if not os.path.isfile(args.file):
        sys.exit(f"File not found: {args.file}")

    load_dotenv(args.env)
    mongo_uri = args.mongo_uri or os.getenv("MONGO_URI")
    if not mongo_uri:
        sys.exit("MONGO_URI not found (checked --mongo-uri and .env).")

    mode = "COMMIT (writing)" if args.commit else "DRY RUN (no writes)"
    # Redact credentials in the printed URI
    safe_uri = re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", mongo_uri)
    print("=" * 72)
    print(f"  Contacts migration  —  {mode}")
    print(f"  File : {args.file}")
    print(f"  Mongo: {safe_uri}")
    print("=" * 72)

    rows, skipped_empty = load_rows(args.file)
    print(f"\nParsed {len(rows)} data rows ({skipped_empty} blank rows skipped).")

    # ── validate required fields ────────────────────────────────────────
    valid, invalid = [], []
    for i, r in enumerate(rows, start=2):  # +2: row1 is header, 1-indexed
        if not r["full_name"] or not r["contact_number_1"]:
            invalid.append((i, r))
        else:
            valid.append(r)
    if invalid:
        print(f"\n⚠ {len(invalid)} row(s) missing full_name or contact_number_1 — these are SKIPPED:")
        for excel_row, r in invalid:
            print(f"    excel row {excel_row}: name={r['full_name']!r} c1={r['contact_number_1']!r}")

    # ── connect ─────────────────────────────────────────────────────────
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=8000)
    if args.db:
        db = client[args.db]
    else:
        try:
            db = client.get_default_database()
        except Exception:
            db = None
        if db is None:
            sys.exit(
                "No database name found. Your MONGO_URI has no /<dbname> in its path.\n"
                "Re-run with --db <name>, e.g.  --db nuvohosting"
            )
    contacts_col = db["contacts"]
    cats_col = db["contact_categories"]
    print(f"Connected. Database: {db.name!r}")
    print(f"Existing contacts in DB: {contacts_col.estimated_document_count()}")

    # ── build set of existing dedup keys from DB ────────────────────────
    existing_keys = set()
    for doc in contacts_col.find({}, {"full_name": 1, "contact_number_1": 1}):
        existing_keys.add(dedup_key(doc.get("full_name", ""), doc.get("contact_number_1", "")))

    # ── decide inserts (dedup vs DB and within-sheet) ───────────────────
    to_insert, dup_db, dup_sheet = [], [], []
    seen_this_run = set()
    for r in valid:
        key = dedup_key(r["full_name"], r["contact_number_1"])
        if key in existing_keys:
            dup_db.append(r)
        elif key in seen_this_run:
            dup_sheet.append(r)
        else:
            seen_this_run.add(key)
            to_insert.append(r)

    # ── categories to create ────────────────────────────────────────────
    existing_cat_names = {norm(c.get("name", "")).lower() for c in cats_col.find({}, {"name": 1})}
    wanted_cats = []
    seen_cat = set()
    for r in to_insert + dup_db:  # consider all categories referenced by the sheet
        c = r["category"]
        if c and c.lower() not in existing_cat_names and c.lower() not in seen_cat:
            seen_cat.add(c.lower())
            wanted_cats.append(c)

    # ── report ──────────────────────────────────────────────────────────
    print("\n" + "-" * 72)
    print("PLAN")
    print("-" * 72)
    print(f"  Contacts to INSERT       : {len(to_insert)}")
    print(f"  Skipped (already in DB)  : {len(dup_db)}")
    print(f"  Skipped (dup within file): {len(dup_sheet)}")
    print(f"  New categories to create : {len(wanted_cats)}  {wanted_cats}")

    if to_insert:
        print("\n  Contacts that will be inserted:")
        print(f"    {'#':>2}  {'NAME':<26}  {'CONTACT-1':<15}  {'CATEGORY':<28}  {'DESIGNATION'}")
        for i, r in enumerate(to_insert, 1):
            print(f"    {i:>2}  {r['full_name'][:26]:<26}  {r['contact_number_1'][:15]:<15}  "
                  f"{r['category'][:28]:<28}  {r['designation']}")
    if dup_db:
        print("\n  Skipped — already present in DB (same name + phone):")
        for r in dup_db:
            print(f"      - {r['full_name']}  ({r['contact_number_1']})")

    # ── commit or stop ──────────────────────────────────────────────────
    if not args.commit:
        print("\n" + "=" * 72)
        print("  DRY RUN complete — nothing was written.")
        print("  Re-run with --commit to insert the above.")
        print("=" * 72)
        return

    print("\nWriting to DB…")
    now = datetime.utcnow()

    # categories first
    if wanted_cats:
        cat_docs = [{"_id": str(uuid.uuid4()), "name": c, "created_at": now} for c in wanted_cats]
        cats_col.insert_many(cat_docs)
        print(f"  ✓ Inserted {len(cat_docs)} categories.")

    # contacts
    if to_insert:
        docs = []
        for r in to_insert:
            docs.append({
                "_id":              str(uuid.uuid4()),
                "category":         r["category"] or None,
                "title":            None,
                "full_name":        r["full_name"],
                "contact_number_1": r["contact_number_1"],
                "contact_number_2": r["contact_number_2"] or None,
                "email":            r["email"] or None,
                "address":          None,
                "company_name":     r["company_name"] or None,
                "department_name":  None,
                "designation":      r["designation"] or None,
                "referred_by":      r["referred_by"] or None,
                "created_at":       now,
                "updated_at":       now,
            })
        contacts_col.insert_many(docs)
        print(f"  ✓ Inserted {len(docs)} contacts.")

    print("\n" + "=" * 72)
    print(f"  DONE. Contacts now in DB: {contacts_col.estimated_document_count()}")
    print("=" * 72)


if __name__ == "__main__":
    main()
