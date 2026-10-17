
from django.contrib import admin

from .models import Appointment, Doctor, Patient, WorkingHours


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "specialty", "is_active")
    list_filter = ("is_active", "specialty")
    search_fields = ("name", "specialty")


@admin.register(WorkingHours)
class WorkingHoursAdmin(admin.ModelAdmin):
    list_display = (
        "doctor",
        "weekday",
        "start_time",
        "end_time",
    )
    list_filter = ("weekday", "doctor")


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "email", "phone_number")
    search_fields = ("full_name", "email", "phone_number")


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "patient",
        "doctor",
        "start_time",
        "end_time",
        "status",
    )
    list_filter = ("status", "doctor")
    search_fields = (
        "patient__full_name",
        "patient__email",
        "doctor__name",
    )
    readonly_fields = ("created_at", "updated_at")
