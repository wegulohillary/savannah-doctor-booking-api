
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Doctor(models.Model):
    name = models.CharField(max_length=150)
    specialty = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.specialty})"


class WorkingHours(models.Model):
    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name="working_hours",
    )
    weekday = models.IntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["weekday", "start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["doctor", "weekday"],
                name="unique_doctor_weekday_hours",
            ),
            models.CheckConstraint(
                condition=Q(start_time__lt=models.F("end_time")),
                name="working_hours_start_before_end",
            ),
        ]

    def clean(self):
        if self.start_time >= self.end_time:
            raise ValidationError(
                "Working hours must end after they start."
            )

    def __str__(self):
        return (
            f"{self.doctor.name}: "
            f"{self.get_weekday_display()} "
            f"{self.start_time}-{self.end_time}"
        )


class Patient(models.Model):
    full_name = models.CharField(max_length=150)
    email = models.EmailField()
    phone_number = models.CharField(max_length=30)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class Appointment(models.Model):
    class Status(models.TextChoices):
        BOOKED = "booked", "Booked"
        CANCELLED = "cancelled", "Cancelled"

    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.BOOKED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_time"]
        constraints = [
            models.CheckConstraint(
                condition=Q(start_time__lt=models.F("end_time")),
                name="appointment_start_before_end",
            ),
            models.UniqueConstraint(
                fields=["doctor", "start_time"],
                condition=Q(status="booked"),
                name="unique_active_doctor_start_time",
            ),
        ]
        indexes = [
            models.Index(
                fields=["doctor", "start_time"],
                name="appt_doctor_start_idx",
            ),
            models.Index(
                fields=["patient", "start_time"],
                name="appt_patient_start_idx",
            ),
            models.Index(
                fields=["status", "start_time"],
                name="appt_status_start_idx",
            ),
        ]

    def clean(self):
        if self.start_time >= self.end_time:
            raise ValidationError(
                "Appointment end time must be after start time."
            )

        if self.start_time and self.end_time:
            duration = self.end_time - self.start_time
            if duration != timedelta(minutes=30):
                raise ValidationError(
                    "Appointments must last 30 minutes."
                )

    def __str__(self):
        return (
            f"{self.patient.full_name} - "
            f"{self.doctor.name} - {self.start_time}"
        )
