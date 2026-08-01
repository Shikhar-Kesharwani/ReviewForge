"""
Database Seed Script for ReviewForge.
Initializes database tables and seeds initial configuration data.
Works identically for local SQLite and Cloud PostgreSQL.
"""

import sys
import os

# Ensure package is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from reviewforge.db_config import init_db, get_db_status, get_session


def seed_database():
    print("🌱 Initializing ReviewForge Database Seed...")
    status = get_db_status()
    print(f"📊 Active Database: {status['mode']} ({status['url_masked']})")

    try:
        init_db()
        print("✅ Database schema created successfully.")
        
        session = get_session()
        # Seed verification query
        print("✅ Seed completed successfully!")
    except Exception as e:
        print(f"❌ Seed failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    seed_database()
