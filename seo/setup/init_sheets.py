#!/usr/bin/env python3
"""
One-time setup script: initializes all Google Sheets tabs with headers.
Run once after creating the spreadsheet and service account.

Usage:
  export GOOGLE_SERVICE_ACCOUNT_JSON='<json content>'
  export GOOGLE_SHEETS_SPREADSHEET_ID='<spreadsheet id>'
  python seo/setup/init_sheets.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sheets import SheetsClient

def main():
    print("Initializing Google Sheets structure...")
    client = SheetsClient()

    if not client.available:
        print("ERROR: Google Sheets not configured.")
        print("Set GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_SHEETS_SPREADSHEET_ID environment variables.")
        sys.exit(1)

    success = client.initialize_all_sheets()
    if success:
        print("All sheets initialized successfully!")
        print(f"Spreadsheet ID: {os.environ.get('GOOGLE_SHEETS_SPREADSHEET_ID')}")
        print("\nSheets created:")
        from config import SHEET_NAMES
        for name in SHEET_NAMES:
            print(f"  ✓ {name}")
    else:
        print("Initialization failed. Check credentials.")
        sys.exit(1)


if __name__ == "__main__":
    main()
