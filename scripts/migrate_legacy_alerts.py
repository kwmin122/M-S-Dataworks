#!/usr/bin/env python3
"""
Legacy Alert Migration Script

Migrates alert_test_*.json files from data/alert_states/ to new format.

Old format:
{
  "keywords": ["keyword1", "keyword2"],
  "regions": ["서울", "경기"],
  "categories": ["category1"]
}

New format:
{
  "email": "...",
  "enabled": false,
  "schedule": "daily_1",
  "hours": [9],
  "rules": [
    {
      "name": "...",
      "keywords": [...],
      "regions": [...],
      "excludeRegions": [],
      "categories": [...],
      "productCodes": [],
      "detailedItems": [],
      "minAmount": null,
      "maxAmount": null
    }
  ],
  "createdAt": "...",
  "updatedAt": "..."
}

Usage:
  python scripts/migrate_legacy_alerts.py          # Perform migration
  python scripts/migrate_legacy_alerts.py --dry-run  # Preview only
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.web_app.alert_storage import save_alert_config

LEGACY_DIR = Path("data/alert_states")
DRY_RUN = False

def is_state_file(data: dict) -> bool:
    """Check if file is a state file (only has last_sent)"""
    return set(data.keys()) == {"last_sent"}

def migrate_config(legacy_data: dict, filename: str) -> dict:
    """Convert legacy format to new format"""
    # Extract email from filename (alert_test_NAME.json -> NAME@test.com)
    # If filename pattern doesn't match, use a default
    name = filename.replace("alert_test_", "").replace(".json", "")
    email = f"{name}@test.com" if name else "unknown@test.com"

    # Build new rule from legacy fields
    rule = {
        "name": f"Legacy rule from {filename}",
        "keywords": legacy_data.get("keywords", []),
        "regions": legacy_data.get("regions", []),
        "excludeRegions": [],  # New field, initialize empty
        "categories": legacy_data.get("categories", []),
        "productCodes": [],    # New field, initialize empty
        "detailedItems": [],   # New field, initialize empty
        "minAmount": legacy_data.get("minAmount"),
        "maxAmount": legacy_data.get("maxAmount"),
    }

    # Build new config
    now = datetime.now(timezone.utc).isoformat()
    new_config = {
        "email": email,
        "enabled": legacy_data.get("enabled", False),
        "schedule": legacy_data.get("schedule", "daily_1"),
        "hours": legacy_data.get("hours", [9]),
        "rules": [rule],
        "createdAt": now,
        "updatedAt": now,
    }

    return new_config

def main():
    global DRY_RUN

    parser = argparse.ArgumentParser(description="Migrate legacy alert configs to new format")
    parser.add_argument("--dry-run", action="store_true", help="Preview migration without saving")
    args = parser.parse_args()

    DRY_RUN = args.dry_run

    if not LEGACY_DIR.exists():
        print(f"❌ Legacy directory not found: {LEGACY_DIR}")
        return 1

    # Find all alert_test_*.json files
    legacy_files = list(LEGACY_DIR.glob("alert_test_*.json"))

    if not legacy_files:
        print(f"✅ No legacy alert files found in {LEGACY_DIR}")
        return 0

    print(f"Found {len(legacy_files)} legacy alert file(s)")
    if DRY_RUN:
        print("🔍 DRY RUN MODE - No changes will be saved\n")
    else:
        print("⚡ MIGRATION MODE - Files will be converted\n")

    migrated_count = 0
    skipped_count = 0
    error_count = 0

    for legacy_file in legacy_files:
        filename = legacy_file.name
        print(f"📄 Processing: {filename}")

        try:
            # Load legacy file
            with open(legacy_file, 'r', encoding='utf-8') as f:
                legacy_data = json.load(f)

            # Skip state files (only have last_sent field)
            if is_state_file(legacy_data):
                print(f"  ⏭️  Skipped (state file, not config)\n")
                skipped_count += 1
                continue

            # Convert to new format
            new_config = migrate_config(legacy_data, filename)

            if DRY_RUN:
                print(f"  ✨ Would migrate:")
                print(f"     Email: {new_config['email']}")
                print(f"     Rules: {len(new_config['rules'])}")
                print(f"     Keywords: {new_config['rules'][0]['keywords']}")
                print(f"     Regions: {new_config['rules'][0]['regions']}")
                print(f"     Categories: {new_config['rules'][0]['categories']}")
                print(f"     New fields: excludeRegions, productCodes, detailedItems (empty)")
                print()
            else:
                # Save using new storage module
                save_alert_config(new_config)
                print(f"  ✅ Migrated to: data/user_alerts/{new_config['email']}")
                print(f"     Email: {new_config['email']}")
                print(f"     Rules: {len(new_config['rules'])}")
                print()

            migrated_count += 1

        except Exception as e:
            print(f"  ❌ Error: {e}\n")
            error_count += 1

    # Summary
    print("=" * 60)
    if DRY_RUN:
        print(f"DRY RUN SUMMARY:")
    else:
        print(f"MIGRATION SUMMARY:")
    print(f"  Migrated: {migrated_count}")
    print(f"  Skipped:  {skipped_count}")
    print(f"  Errors:   {error_count}")
    print("=" * 60)

    if DRY_RUN and migrated_count > 0:
        print("\n💡 Run without --dry-run to perform actual migration")

    return 0 if error_count == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
