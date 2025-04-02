#!/usr/bin/env python
"""
Script to create a backup of the database.
Run this script manually or via a scheduled task to create database backups.
"""
import os
import sys
import shutil
import datetime
from pathlib import Path

# Get the project's base directory
BASE_DIR = Path(__file__).resolve().parent

def create_backup():
    """Create a backup of the database file."""
    # Define paths
    db_path = BASE_DIR / 'db.sqlite3'
    backup_dir = BASE_DIR / 'backup'
    
    # Create backup directory if it doesn't exist
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    # Check if database file exists
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        return False
    
    try:
        # Create a timestamped backup for archival purposes
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        archive_backup_path = backup_dir / f"db_{timestamp}.sqlite3"
        
        # Copy the database to the archive backup
        shutil.copy2(db_path, archive_backup_path)
        
        # Also create/update the main backup that will be used for restoration
        main_backup_path = backup_dir / 'db.sqlite3'
        shutil.copy2(db_path, main_backup_path)
        
        print(f"Backup created successfully:")
        print(f"  - Main backup: {main_backup_path}")
        print(f"  - Archive copy: {archive_backup_path}")
        return True
        
    except Exception as e:
        print(f"Error creating backup: {str(e)}")
        return False

if __name__ == "__main__":
    print("Creating database backup...")
    success = create_backup()
    sys.exit(0 if success else 1) 