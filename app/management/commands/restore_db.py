import os
import boto3
import tempfile
import traceback
from django.conf import settings
from django.core.management import call_command, BaseCommand
from django.core.mail import send_mail

EXCLUDED_MODELS = ['contenttypes.contenttype', 'auth.permission', 'auth.group', 'admin.logentry', 'sessions.session']
BUCKET_NAME = settings.AWS_STORAGE_BUCKET_NAME
S3_FOLDER = 'backups/'

class Command(BaseCommand):
    help = 'Safely restore DB from a JSON fixture, skipping system tables and fixing dependencies.'

    def add_arguments(self, parser):
        parser.add_argument('filename', type=str, help='Name of the JSON backup file')
        parser.add_argument('--s3', action='store_true', help='Load backup file from S3')
        parser.add_argument('--path', type=str, default='', help='Optional subfolder in S3')

    def handle(self, *args, **options):
        filename = options['filename']
        use_s3 = options['s3']
        s3_path = os.path.join(options['path'], filename) if options['path'] else f"{S3_FOLDER}{filename}"

        subject = ''
        message = ''

        try:
            if use_s3:
                self.stdout.write(self.style.NOTICE(f"Downloading `{s3_path}` from S3..."))
                s3 = boto3.client('s3')
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    s3.download_fileobj(BUCKET_NAME, s3_path, temp_file)
                    temp_file_path = temp_file.name
            else:
                temp_file_path = os.path.join(settings.BASE_DIR, 'backups', filename)
                if not os.path.exists(temp_file_path):
                    raise FileNotFoundError(f"Local backup file not found: {temp_file_path}")

            self.stdout.write(self.style.NOTICE("Running migrate to ensure schema is ready..."))
            call_command('migrate', verbosity=0)

            self.stdout.write(self.style.NOTICE("Loading fixture..."))
            call_command('loaddata', temp_file_path, exclude=EXCLUDED_MODELS, verbosity=1)

            self.stdout.write(self.style.NOTICE("Finalizing with another migrate to rebuild system tables..."))
            call_command('migrate', verbosity=0)

            subject = "✅ Database Restore Successful"
            message = f"The backup `{filename}` was restored successfully."

            self.stdout.write(self.style.SUCCESS(message))

        except Exception as e:
            subject = "❌ Database Restore Failed"
            message = f"An error occurred while restoring `{filename}`:\n\n{traceback.format_exc()}"
            self.stderr.write(self.style.ERROR(message))

        # Email summary
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [settings.DEFAULT_FROM_EMAIL],
            fail_silently=False
        )


#  Restore from local backup:
# python manage.py restore_db_safe backup_20250802_142300.json
#
#
#  Restore from S3 backup:
# python manage.py restore_db backup_20250802_142300.json --s3
