
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from appointments.models import (
    Appointment,
    Doctor,
    Patient,
    WorkingHours,
)


NAIROBI = ZoneInfo("Africa/Nairobi")


class AppointmentAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.doctor = Doctor.objects.create(
            name="Dr. Test",
            specialty="General Practice",
            is_active=True,
        )

        # Use a future weekday so the tests do not depend on
        # which day of the week they are executed.
        self.booking_date = date.today() + timedelta(days=1)
        while self.booking_date.weekday() >= 5:
            self.booking_date += timedelta(days=1)

        self.start_time = datetime.combine(
            self.booking_date,
            time(10, 0),
            tzinfo=NAIROBI,
        )

        WorkingHours.objects.create(
            doctor=self.doctor,
            weekday=self.booking_date.weekday(),
            start_time=time(9, 0),
            end_time=time(17, 0),
        )

    def booking_payload(self, start_time=None):
        return {
            "doctor_id": self.doctor.id,
            "patient_name": "Jane Test",
            "patient_email": "jane@example.com",
            "patient_phone": "+254700000000",
            "start_time": (
                start_time or self.start_time
            ).isoformat(),
        }

    def book(self, start_time=None):
        return self.client.post(
            "/api/appointments/",
            self.booking_payload(start_time),
            format="json",
        )

    def test_list_doctors_returns_active_doctors(self):
        Doctor.objects.create(
            name="Dr. Inactive",
            specialty="Dermatology",
            is_active=False,
        )

        response = self.client.get("/api/doctors/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Dr. Test")

    def test_booking_creates_appointment(self):
        response = self.book()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Appointment.objects.count(), 1)
        self.assertEqual(Patient.objects.count(), 1)

        appointment = Appointment.objects.get()
        self.assertEqual(appointment.doctor, self.doctor)
        self.assertEqual(appointment.status, "booked")
        self.assertEqual(
            appointment.patient.full_name,
            "Jane Test",
        )

    def test_booking_within_one_hour_is_rejected(self):
        too_soon = timezone.now() + timedelta(minutes=30)

        response = self.book(too_soon)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Appointment.objects.count(), 0)

    def test_duplicate_booking_is_rejected(self):
        first = self.book()
        second = self.book()

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_booking_outside_working_hours_is_rejected(self):
        outside_hours = self.start_time.replace(
            hour=17,
            minute=0,
        )

        response = self.book(outside_hours)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Appointment.objects.count(), 0)

    def test_availability_endpoint_returns_slots(self):
        response = self.client.get(
            f"/api/doctors/{self.doctor.id}/availability/",
            {"date": self.booking_date.isoformat()},
        )

        self.assertEqual(response.status_code, 200)

    def test_upcoming_appointments_are_sorted(self):
        later_start = self.start_time + timedelta(minutes=60)

        # Create valid records directly so this test focuses
        # on the upcoming endpoint's filtering and ordering.
        patient1 = Patient.objects.create(
            full_name="Later Patient",
            email="later@example.com",
            phone_number="+254700000001",
        )
        patient2 = Patient.objects.create(
            full_name="Earlier Patient",
            email="earlier@example.com",
            phone_number="+254700000002",
        )

        Appointment.objects.create(
            doctor=self.doctor,
            patient=patient1,
            start_time=later_start,
            end_time=later_start + timedelta(minutes=30),
            status="booked",
        )
        Appointment.objects.create(
            doctor=self.doctor,
            patient=patient2,
            start_time=self.start_time,
            end_time=self.start_time + timedelta(minutes=30),
            status="booked",
        )

        response = self.client.get(
            "/api/appointments/upcoming/"
        )

        self.assertEqual(response.status_code, 200)

        returned_times = [
            datetime.fromisoformat(item["start_time"])
            for item in response.data
        ]

        self.assertEqual(returned_times, sorted(returned_times))

    def test_cancelled_appointment_is_not_a_booked_slot(self):
        response = self.book()
        self.assertEqual(response.status_code, 201)

        appointment_id = response.data["id"]

        cancel_response = self.client.patch(
            f"/api/appointments/{appointment_id}/cancel/"
        )

        self.assertEqual(cancel_response.status_code, 200)

        appointment = Appointment.objects.get(
            id=appointment_id
        )
        self.assertEqual(appointment.status, "cancelled")

def test_reschedule_appointment(self):
    booking_response = self.book()
    self.assertEqual(booking_response.status_code, 201)

    appointment_id = booking_response.data["id"]
    new_start = self.start_time + timedelta(minutes=30)

    response = self.client.patch(
        f"/api/appointments/{appointment_id}/reschedule/",
        {"start_time": new_start.isoformat()},
        format="json",
    )

    self.assertEqual(response.status_code, 200)

    appointment = Appointment.objects.get(id=appointment_id)

    self.assertEqual(
        appointment.start_time,
        new_start,
    )