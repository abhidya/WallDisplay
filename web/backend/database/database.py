import os
from sqlalchemy import create_engine, MetaData, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging

logger = logging.getLogger(__name__)

# Get database URL from environment variable or use default SQLite database
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./nanodlna.db")

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a single MetaData instance
# This will be shared across all modules that import Base
metadata_obj = MetaData()

# Pass the shared MetaData instance to declarative_base
Base = declarative_base(metadata=metadata_obj)

# Models will be imported in init_db() to avoid circular imports


def _sqlite_column_names(connection, table_name):
    rows = connection.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
    return [row[1] for row in rows]


def ensure_sqlite_schema_compatibility():
    """
    Keep older SQLite databases bootable when models add columns/tables.

    This is intentionally lightweight and only handles additive compatibility
    for the mapping/media-library upgrade. The standalone migration script is
    still the formal path for explicit schema upgrades.
    """
    if not DATABASE_URL.startswith("sqlite"):
        return

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    with engine.begin() as connection:
        if "videos" in tables:
            video_columns = set(_sqlite_column_names(connection, "videos"))
            if "category" not in video_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE videos ADD COLUMN category VARCHAR NOT NULL DEFAULT 'background'"
                )
            if "source_type" not in video_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE videos ADD COLUMN source_type VARCHAR NOT NULL DEFAULT 'upload'"
                )
            if "source_directory_id" not in video_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE videos ADD COLUMN source_directory_id INTEGER"
                )
            if "preprocessing_status" not in video_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE videos ADD COLUMN preprocessing_status VARCHAR NOT NULL DEFAULT 'pending'"
                )
            if "preprocessing_error" not in video_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE videos ADD COLUMN preprocessing_error VARCHAR"
                )
            if "overlay_optimized" not in video_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE videos ADD COLUMN overlay_optimized BOOLEAN NOT NULL DEFAULT 0"
                )

        if "overlay_configs" in tables:
            overlay_columns = set(_sqlite_column_names(connection, "overlay_configs"))
            if "background_type" not in overlay_columns or "mapping_scene_id" not in overlay_columns:
                connection.exec_driver_sql(
                    """
                    CREATE TABLE IF NOT EXISTS overlay_configs_new (
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
                connection.exec_driver_sql(
                    """
                    INSERT INTO overlay_configs_new (
                        id, name, background_type, video_id, mapping_scene_id, video_transform, widgets, api_configs, created_at, updated_at
                    )
                    SELECT id, name, 'video', video_id, NULL, video_transform, widgets, api_configs, created_at, updated_at
                    FROM overlay_configs
                    """
                )
                connection.exec_driver_sql("DROP TABLE overlay_configs")
                connection.exec_driver_sql("ALTER TABLE overlay_configs_new RENAME TO overlay_configs")
                connection.exec_driver_sql(
                    "CREATE INDEX IF NOT EXISTS idx_overlay_configs_video_id ON overlay_configs(video_id)"
                )
                connection.exec_driver_sql(
                    "CREATE INDEX IF NOT EXISTS idx_overlay_configs_mapping_scene_id ON overlay_configs(mapping_scene_id)"
                )

        connection.exec_driver_sql(
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
        connection.exec_driver_sql(
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
        connection.exec_driver_sql(
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
        connection.exec_driver_sql(
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
        connection.exec_driver_sql(
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
        connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR NOT NULL,
                path VARCHAR NOT NULL UNIQUE,
                file_name VARCHAR,
                file_size INTEGER,
                format VARCHAR,
                resolution VARCHAR,
                category VARCHAR NOT NULL DEFAULT 'background',
                source_type VARCHAR NOT NULL DEFAULT 'upload',
                source_directory_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS photo_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR NOT NULL UNIQUE,
                category VARCHAR NOT NULL DEFAULT 'background',
                photo_ids JSON NOT NULL DEFAULT '[]',
                playback_mode VARCHAR NOT NULL DEFAULT 'sequence',
                shuffle VARCHAR NOT NULL DEFAULT 'false',
                loop VARCHAR NOT NULL DEFAULT 'true',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

def get_db():
    """
    Get a database session
    
    Yields:
        Session: Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    Initialize the database
    """
    # Import models here to ensure they are registered with Base.metadata
    # This avoids circular imports since this function is called after all modules are loaded
    from models.device import DeviceModel
    from models.video import VideoModel
    from models.overlay import OverlayConfig
    from models.projection import ProjectionConfig
    from models.mapping_scene import MappingScene
    from models.scene_rank import SceneRank
    from models.media_directory import MediaDirectory
    from models.media_list import MediaList
    from models.media_channel import MediaChannel
    from models.photo import PhotoModel
    from models.photo_list import PhotoList
    
    # When running under pytest, skip the actual Base.metadata.create_all(bind=engine) call.
    # The test fixtures will handle creating tables on the temporary test database.
    if "PYTEST_CURRENT_TEST" in os.environ:
        logger.info("Skipping full DB DDL initialization during pytest run. Test fixtures will manage tables.")
        return  # Skip create_all for production engine

    try:
        Base.metadata.create_all(bind=engine) # This uses the production engine
        ensure_sqlite_schema_compatibility()
        logger.info("Database initialized for production/development")
    except Exception as e:
        logger.error(f"Error initializing database for production/development: {e}")
        raise
