import os
import subprocess
import datetime
import traceback
from django.conf import settings
from django.core.management.base import BaseCommand

BACKUP_DIR = os.path.join(settings.BASE_DIR, 'backups')
NUM_BACKUPS_TO_KEEP = 3  # Not used in dry run, but retained for consistency

class Command(BaseCommand):
    help = 'Dry-run: Backup database to local JSON file only (no S3, no email).'

    def handle(self, *args, **options):
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'backup_{timestamp}.json'
        local_path = os.path.join(BACKUP_DIR, filename)

        self.stdout.write(self.style.WARNING("🧪 Running DRY RUN database backup (local only)..."))

        try:
            os.makedirs(BACKUP_DIR, exist_ok=True)

            # Dump DB to local file
            subprocess.run([
                'python', 'manage.py', 'dumpdata',
                '--exclude=contenttypes',
                '--exclude=auth.permission',
                '--exclude=auth.group',
                '--exclude=admin.logentry',
                '--exclude=sessions',
                '--natural-foreign',
                '--natural-primary',
                '--indent=2',
                '-o', local_path
            ], check=True)

            self.stdout.write(self.style.SUCCESS(f"✅ DRY RUN Success: Backup saved to {local_path}"))

        except subprocess.CalledProcessError as e:
            self.stderr.write(self.style.ERROR(f"❌ DRY RUN Error running dumpdata:\n{e}"))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ DRY RUN Exception:\n{traceback.format_exc()}"))
