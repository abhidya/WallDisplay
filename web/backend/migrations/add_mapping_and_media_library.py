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


def column_names(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def ensure_video_columns(cursor):
    columns = column_names(cursor, "videos")
    if "category" not in columns:
        cursor.execute("ALTER TABLE videos ADD COLUMN category VARCHAR NOT NULL DEFAULT 'background'")
    if "source_type" not in columns:
        cursor.execute("ALTER TABLE videos ADD COLUMN source_type VARCHAR NOT NULL DEFAULT 'upload'")
    if "source_directory_id" not in columns:
        cursor.execute("ALTER TABLE videos ADD COLUMN source_directory_id INTEGER")


def rebuild_overlay_configs(cursor):
    columns = column_names(cursor, "overlay_configs")
    if "background_type" in columns and "mapping_scene_id" in columns:
        return

    cursor.execute(
        """
        CREATE TABLE overlay_configs_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR NOT NULL,
            background_type VARCHAR NOT NULL DEFAULT 'video',
            video_id INTEGER,
            mapping_scene_id INTEGER,
            video_transform JSON NOT NULL,
            widgets JSON NOT NULL,
            api_configs JSON NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        INSERT INTO overlay_configs_new (
            id, name, background_type, video_id, mapping_scene_id, video_transform, widgets, api_configs, created_at, updated_at
        )
        SELECT id, name, 'video', video_id, NULL, video_transform, widgets, api_configs, created_at, updated_at
        FROM overlay_configs
        """
    )
    cursor.execute("DROP TABLE overlay_configs")
    cursor.execute("ALTER TABLE overlay_configs_new RENAME TO overlay_configs")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_overlay_configs_video_id ON overlay_configs(video_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_overlay_configs_mapping_scene_id ON overlay_configs(mapping_scene_id)")


def create_media_tables(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS mapping_scenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR NOT NULL UNIQUE,
            canvas_width INTEGER NOT NULL DEFAULT 1280,
            canvas_height INTEGER NOT NULL DEFAULT 720,
            mask_mode VARCHAR NOT NULL DEFAULT 'luminance',
            masks JSON NOT NULL DEFAULT '[]',
            groups JSON NOT NULL DEFAULT '[]',
            render_settings JSON NOT NULL DEFAULT '{}',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS scene_ranks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR NOT NULL UNIQUE,
            orientation VARCHAR NOT NULL DEFAULT 'horizontal',
            scene_ids JSON NOT NULL DEFAULT '[]',
            gap_px INTEGER NOT NULL DEFAULT 0,
            rank_metadata JSON NOT NULL DEFAULT '{}',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS media_directories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR NOT NULL UNIQUE,
            path VARCHAR NOT NULL UNIQUE,
            category VARCHAR NOT NULL DEFAULT 'background',
            enabled BOOLEAN NOT NULL DEFAULT 1,
            scan_mode VARCHAR NOT NULL DEFAULT 'recursive',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS media_lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR NOT NULL UNIQUE,
            category VARCHAR NOT NULL DEFAULT 'background',
            video_ids JSON NOT NULL DEFAULT '[]',
            playback_mode VARCHAR NOT NULL DEFAULT 'sequence',
            shuffle VARCHAR NOT NULL DEFAULT 'false',
            loop VARCHAR NOT NULL DEFAULT 'true',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS media_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR NOT NULL UNIQUE,
            media_list_id INTEGER NOT NULL,
            current_video_id INTEGER,
            current_index INTEGER NOT NULL DEFAULT 0,
            playback_state JSON NOT NULL DEFAULT '{}',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (media_list_id) REFERENCES media_lists (id) ON DELETE CASCADE
        )
        """
    )


def main():
    db_path = find_db_path()
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        ensure_video_columns(cursor)
        rebuild_overlay_configs(cursor)
        create_media_tables(cursor)
        conn.commit()
        print(f"Migration completed successfully for {db_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
