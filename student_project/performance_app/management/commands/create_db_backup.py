import os
import shutil
import datetime
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Creates a backup of the SQLite database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-timestamp',
            action='store_true',
            help='Do not create a timestamped archive copy',
        )

    def handle(self, *args, **options):
        # Define paths
        db_path = settings.DATABASES['default']['NAME']
        backup_dir = os.path.join(settings.BASE_DIR, 'backup')
        
        # Create backup directory if it doesn't exist
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            self.stdout.write(self.style.SUCCESS(f"Created backup directory at {backup_dir}"))
        
        # Check if database file exists
        if not os.path.exists(db_path):
            self.stdout.write(self.style.ERROR(f"Database file not found at {db_path}"))
            return
        
        try:
            # Create the main backup that will be used for restoration
            main_backup_path = os.path.join(backup_dir, 'db.sqlite3')
            shutil.copy2(db_path, main_backup_path)
            self.stdout.write(self.style.SUCCESS(f"Main backup created at {main_backup_path}"))
            
            # Create a timestamped backup for archival purposes (unless --no-timestamp is specified)
            if not options['no_timestamp']:
                timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                archive_backup_path = os.path.join(backup_dir, f"db_{timestamp}.sqlite3")
                shutil.copy2(db_path, archive_backup_path)
                self.stdout.write(self.style.SUCCESS(f"Archive backup created at {archive_backup_path}"))
            
            self.stdout.write(self.style.SUCCESS("Database backup completed successfully"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error creating backup: {str(e)}")) 