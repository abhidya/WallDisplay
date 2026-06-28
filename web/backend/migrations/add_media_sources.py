#!/usr/bin/env python3
import os
import sqlite3


def find_db_path():
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "nanodlna.db"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "nano_dlna.db"),
        "./nanodlna.db",
        "./nano_dlna.db",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    raise FileNotFoundError("Could not locate SQLite database")


def create_media_source_tables(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS media_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider VARCHAR NOT NULL UNIQUE,
            display_name VARCHAR NOT NULL,
            enabled BOOLEAN NOT NULL DEFAULT 1,
            status VARCHAR NOT NULL DEFAULT 'idle',
            item_count INTEGER NOT NULL DEFAULT 0,
            last_refresh_at DATETIME,
            last_success_at DATETIME,
            last_error TEXT,
            backoff_until DATETIME,
            etag VARCHAR,
            last_modified VARCHAR,
            config JSON NOT NULL DEFAULT '{}',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS media_source_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider VARCHAR NOT NULL,
            canonical_url VARCHAR NOT NULL,
            title VARCHAR NOT NULL,
            page_url VARCHAR NOT NULL,
            thumbnail_url VARCHAR,
            media_url VARCHAR,
            category VARCHAR,
            tags JSON NOT NULL DEFAULT '[]',
            cache_key VARCHAR NOT NULL,
            cache_status VARCHAR NOT NULL DEFAULT 'fresh',
            import_status VARCHAR NOT NULL DEFAULT 'not_imported',
            imported_video_id INTEGER,
            http_etag VARCHAR,
            http_last_modified VARCHAR,
            failure_reason TEXT,
            failed_at DATETIME,
            next_retry_at DATETIME,
            discovered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME,
            last_checked_at DATETIME,
            CONSTRAINT uq_media_source_provider_canonical_url UNIQUE (provider, canonical_url)
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_source_entries_provider ON media_source_entries(provider)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_source_entries_cache_key ON media_source_entries(cache_key)")


def main():
    db_path = find_db_path()
    conn = sqlite3.connect(db_path)
    try:
        create_media_source_tables(conn.cursor())
        conn.commit()
        print(f"Migration completed successfully for {db_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
