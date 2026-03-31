#!/usr/bin/env python3
"""
Script to add videos from my_device_config.json to the database.
"""

import os
import sys
import json
import logging
import sqlite3

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

def add_config_videos(config_path, db_path):
    """
    Add videos from the configuration file to the database.
    
    Args:
        config_path: Path to the configuration file
        db_path: Path to the SQLite database file
    """
    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found: {config_path}")
        return False
    
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return False
    
    try:
        # Load the configuration file
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Extract video paths from the configuration
        config_dir = os.path.dirname(os.path.abspath(config_path))
        video_paths = []
        for device in config:
            if "video_file" in device and device["video_file"]:
                video_path = os.path.expanduser(os.path.expandvars(device["video_file"]))
                if not os.path.isabs(video_path):
                    video_path = os.path.abspath(os.path.join(config_dir, video_path))
                if os.path.exists(video_path):
                    video_paths.append(video_path)
                    logger.info(f"Found video path in config: {video_path}")
                else:
                    logger.warning(f"Video path does not exist: {video_path}")
        
        if not video_paths:
            logger.warning("No valid video paths found in the configuration")
            return False
        
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create the videos table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                path TEXT NOT NULL,
                file_name TEXT,
                file_size INTEGER,
                duration REAL,
                format TEXT,
                resolution TEXT,
                has_subtitle BOOLEAN DEFAULT 0,
                subtitle_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Discover current videos table columns so inserts stay compatible across schema versions.
        cursor.execute("PRAGMA table_info(videos)")
        table_columns = {row[1] for row in cursor.fetchall()}

        # Add videos to the database
        videos_added = 0
        for video_path in video_paths:
            # Check if the video already exists in the database
            cursor.execute("SELECT id FROM videos WHERE path = ?", (video_path,))
            existing_video = cursor.fetchone()
            
            if existing_video:
                logger.info(f"Video already exists in database: {video_path}")
                continue
            
            # Get video information
            file_name = os.path.basename(video_path)
            name = os.path.splitext(file_name)[0]
            file_size = os.path.getsize(video_path)
            
            # Insert the video into the database.
            insert_values = {
                "name": name,
                "path": video_path,
                "file_name": file_name,
                "file_size": file_size,
                "has_subtitle": False,
                "category": "background",
                "source_type": "config",
                "source_directory_id": None,
                "preprocessing_status": "pending",
                "preprocessing_error": None,
                "overlay_optimized": False,
                "subtitle_path": None,
            }
            selected_columns = [col for col in insert_values.keys() if col in table_columns]
            placeholders = ", ".join(["?"] * len(selected_columns))
            column_clause = ", ".join(selected_columns)
            values = [insert_values[col] for col in selected_columns]
            cursor.execute(
                f"INSERT INTO videos ({column_clause}) VALUES ({placeholders})",
                values,
            )
            
            videos_added += 1
            logger.info(f"Added video to database: {name} ({video_path})")
        
        # Commit the changes
        conn.commit()
        logger.info(f"Added {videos_added} videos to the database")
        
        # Get the final count of videos
        cursor.execute("SELECT COUNT(*) FROM videos")
        final_count = cursor.fetchone()[0]
        logger.info(f"Final video count: {final_count}")
        
        # Close the connection
        conn.close()
        
        return True
    except Exception as e:
        logger.error(f"Error adding videos from config: {e}")
        return False

if __name__ == "__main__":
    # Get the paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Default config path
    config_path = os.path.join(script_dir, "my_device_config.json")
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    
    # Default database path
    db_path = os.path.join(script_dir, "web", "backend", "nanodlna.db")
    if len(sys.argv) > 2:
        db_path = sys.argv[2]
    
    logger.info(f"Using config at {config_path}")
    logger.info(f"Using database at {db_path}")
    add_config_videos(config_path, db_path)
