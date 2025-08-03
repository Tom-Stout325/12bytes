from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from django.contrib import messages
from django.conf import settings
from datetime import datetime
import boto3, os

from .models import BackupProxy  

from dataclasses import dataclass

@dataclass
class Backup:
    filename: str
    size_kb: float
    timestamp: str
    location: str  # 'local' or 's3'


class BackupAdmin(admin.ModelAdmin):
    change_list_template = "admin/app/backup_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('backup/', self.admin_site.admin_view(self.create_backup), name='create-backup'),
            path('restore/<str:filename>/', self.admin_site.admin_view(self.restore_backup), name='restore-backup'),
            path('delete_old/', self.admin_site.admin_view(self.delete_old_backups), name='delete-old-backups'),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        s3 = boto3.client("s3")
        bucket = settings.AWS_STORAGE_BUCKET_NAME
        prefix = "backups/"

        objects = s3.list_objects_v2(Bucket=bucket, Prefix=prefix).get('Contents', [])

        backups = []
        for obj in sorted(objects, key=lambda x: x["LastModified"], reverse=True):
            name = obj["Key"]
            ts = name.replace("backup_", "").replace(".json", "")
            try:
                parsed_ts = datetime.strptime(ts, "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
            except:
                parsed_ts = "Unknown"

            backups.append(Backup(
                filename=name,
                size_kb=round(obj["Size"] / 1024, 1),
                timestamp=parsed_ts,
                location="s3"
            ))

        return super().changelist_view(request, extra_context={"backups": backups})

    def create_backup(self, request):
        from django.core.management import call_command
        try:
            call_command("backup_db")
            self.message_user(request, "✅ Backup created successfully!", level=messages.SUCCESS)
        except Exception as e:
            self.message_user(request, f"❌ Backup failed: {e}", level=messages.ERROR)
        return redirect("..")

    def restore_backup(self, request, filename):
        from django.core.management import call_command
        try:
            call_command("restore_db_safe", filename, "--s3")
            self.message_user(request, f"✅ Restored: {filename}", level=messages.SUCCESS)
        except Exception as e:
            self.message_user(request, f"❌ Restore failed: {e}", level=messages.ERROR)
        return redirect("..")

    def delete_old_backups(self, request):
        s3 = boto3.client("s3")
        bucket = settings.AWS_STORAGE_BUCKET_NAME
        prefix = "backups/"
        max_keep = 3

        objects = s3.list_objects_v2(Bucket=bucket, Prefix=prefix).get("Contents", [])
        backups = sorted([obj["Key"] for obj in objects if obj["Key"].endswith(".json")])

        to_delete = backups[:-max_keep]
        for key in to_delete:
            s3.delete_object(Bucket=bucket, Key=key)

        self.message_user(request, f"🗑 Deleted {len(to_delete)} old backups.", level=messages.SUCCESS)
        return redirect("..")


admin.site.register(BackupProxy, BackupAdmin)
