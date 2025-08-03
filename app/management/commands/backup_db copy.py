import os
import subprocess
import datetime
import boto3
import traceback
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.mail import send_mail

BACKUP_DIR = os.path.join(settings.BASE_DIR, 'backups')
BUCKET_NAME = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None)
if not BUCKET_NAME:
    raise Exception("AWS_STORAGE_BUCKET_NAME is not defined in settings.")

S3_FOLDER = 'backups/'
NUM_BACKUPS_TO_KEEP = 3

class Command(BaseCommand):
    help = 'Backup database to local and S3, clean old backups, and email result.'

    def handle(self, *args, **options):
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'backup_{timestamp}.json'
        local_path = os.path.join(BACKUP_DIR, filename)
        s3_path = f'{S3_FOLDER}{filename}'
        subject = ''
        message = ''

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

            # Upload to S3
            s3 = boto3.client('s3')
            s3.upload_file(local_path, BUCKET_NAME, s3_path)

            # Clean up local backups
            local_backups = sorted(
                [f for f in os.listdir(BACKUP_DIR) if f.startswith('backup_') and f.endswith('.json')],
                reverse=True
            )
            for old in local_backups[NUM_BACKUPS_TO_KEEP:]:
                os.remove(os.path.join(BACKUP_DIR, old))

            # Clean up S3 backups
            s3_objects = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=S3_FOLDER).get('Contents', [])
            s3_backups = sorted(
                [obj['Key'] for obj in s3_objects if obj['Key'].endswith('.json')],
                reverse=True
            )
            for old_key in s3_backups[NUM_BACKUPS_TO_KEEP:]:
                s3.delete_object(Bucket=BUCKET_NAME, Key=old_key)

            subject = "✅ Database Backup Successful"
            message = f"The backup `{filename}` was created and uploaded successfully."

        except Exception as e:
            subject = "❌ Database Backup Failed"
            message = f"An error occurred during backup:\n\n{traceback.format_exc()}"

        # Send email notification
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [settings.DEFAULT_FROM_EMAIL],
            fail_silently=False,
        )
