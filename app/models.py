from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now
from drones.models import FlightLog

from dataclasses import dataclass


# A real (non-abstract) base model for the proxy
class BackupBase(models.Model):
    dummy = models.BooleanField(default=False)  # required to make it concrete

    class Meta:
        db_table = 'backup_base'  # optional, but avoids table name conflicts

# Proxy model
class BackupProxy(BackupBase):
    class Meta:
        proxy = True
        verbose_name = "Database Backup"
        verbose_name_plural = "Database Backups"

    def __str__(self):
        return "Backup Tool"

# Used only in admin logic for parsing backup files
@dataclass
class Backup:
    filename: str
    size_kb: float
    timestamp: str
    location: str





def training_certificate_upload_path(instance, filename):
    return f"training_certificates/{instance.pilot.user.username}/{filename}"


class Training(models.Model):
    pilot = models.ForeignKey('PilotProfile', on_delete=models.CASCADE, related_name='trainings')
    title = models.CharField(max_length=200)
    date_completed = models.DateField()
    required = models.BooleanField(default=False)
    certificate = models.ImageField(upload_to=training_certificate_upload_path, blank=True, null=True)

    class Meta:
        ordering = ['-date_completed']

    def __str__(self):
        return f"{self.title} ({self.date_completed})"



def license_upload_path(instance, filename):
    return f"pilot_licenses/{instance.user.username}/{filename}"
    

class PilotProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    license_number = models.CharField(max_length=100, blank=True, null=True)
    license_date = models.DateField(blank=True, null=True)
    license_image = models.ImageField(upload_to=license_upload_path, blank=True, null=True)

    def flights_this_year(self):
        return FlightLog.objects.filter(
            pilot_in_command__iexact=f"{self.user.first_name} {self.user.last_name}",
            flight_date__year=now().year
        ).count()

    def flights_total(self):
        return FlightLog.objects.filter(
            pilot_in_command__iexact=f"{self.user.first_name} {self.user.last_name}"
        ).count()

    def flight_time_this_year(self):
        logs = FlightLog.objects.filter(
            pilot_in_command__iexact=f"{self.user.first_name} {self.user.last_name}",
            flight_date__year=now().year
        ).values_list("air_time", flat=True)
        return sum((t.total_seconds() for t in logs if t), 0)

    def flight_time_total(self):
        logs = FlightLog.objects.filter(
            pilot_in_command__iexact=f"{self.user.first_name} {self.user.last_name}"
        ).values_list("air_time", flat=True)
        return sum((t.total_seconds() for t in logs if t), 0)

    def __str__(self):
        return self.user.username
    



