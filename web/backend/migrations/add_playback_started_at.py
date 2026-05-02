#!/usr/bin/env python3
"""
Add playback_started_at field to devices table
"""
import logging
import sys
import os

# Add parent directories to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)

from sqlalchemy import create_engine, text
from web.backend.database.database import DATABASE_URL

logger = logging.getLogger(__name__)

def upgrade():
    """Add playback_started_at field to devices table"""
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        try:
            # Add playback_started_at column
            conn.execute(text("""
                ALTER TABLE devices 
                ADD COLUMN playback_started_at TIMESTAMP WITH TIME ZONE
            """))
            conn.commit()
            logger.info("Added playback_started_at column to devices table")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                logger.info("playback_started_at column already exists")
            else:
                raise

def downgrade():
    """Remove playback_started_at field from devices table"""
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE devices DROP COLUMN playback_started_at"))
        conn.commit()

if __name__ == "__main__":
    upgrade()
    print("Migration completed successfully")