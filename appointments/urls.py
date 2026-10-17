
from django.urls import path

from appointments.views import (
    AppointmentCancelView,
    AppointmentCreateView,
    AppointmentDetailView,
    AppointmentRescheduleView,
    DoctorAvailabilityView,
    DoctorListView,
    UpcomingAppointmentsView,
)

urlpatterns = [
    path(
        "doctors/",
        DoctorListView.as_view(),
        name="doctor-list",
    ),
    path(
        "doctors/<int:doctor_id>/availability/",
        DoctorAvailabilityView.as_view(),
        name="doctor-availability",
    ),
    path(
        "appointments/",
        AppointmentCreateView.as_view(),
        name="appointment-create",
    ),
    path(
        "appointments/upcoming/",
        UpcomingAppointmentsView.as_view(),
        name="upcoming-appointments",
    ),
    path(
        "appointments/<int:pk>/",
        AppointmentDetailView.as_view(),
        name="appointment-detail",
    ),
    path(
        "appointments/<int:appointment_id>/cancel/",
        AppointmentCancelView.as_view(),
        name="appointment-cancel",
    ),
    path(
        "appointments/<int:appointment_id>/reschedule/",
        AppointmentRescheduleView.as_view(),
        name="appointment-reschedule",
    ),
]
