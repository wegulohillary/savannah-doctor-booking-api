
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta
from threading import Barrier
from unittest import skipUnless
from zoneinfo import ZoneInfo

from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from appointments.models import Appointment, Doctor, WorkingHours


NAIROBI = ZoneInfo("Africa/Nairobi")


@skipUnless(
    connection.features.has_select_for_update,
    "Concurrency test requires SELECT FOR UPDATE support.",
)
class ConcurrentBookingTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.doctor = Doctor.objects.create(
            name="Dr. Concurrent",
            specialty="General Practice",
            is_active=True,
        )

        self.booking_date = timezone.localdate() + timedelta(days=1)
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

    def make_booking(self, index, barrier):
        close_old_connections()
        try:
            client = APIClient()
            barrier.wait(timeout=10)

            response = client.post(
                "/api/appointments/",
                {
                    "doctor_id": self.doctor.id,
                    "patient_name": f"Concurrent Patient {index}",
                    "patient_email": f"concurrent{index}@example.com",
                    "patient_phone": f"+2547000000{20 + index}",
                    "start_time": self.start_time.isoformat(),
                },
                format="json",
            )
            return response.status_code
        finally:
            close_old_connections()

    def test_simultaneous_requests_cannot_double_book_slot(self):
        barrier = Barrier(2)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(self.make_booking, i, barrier)
                for i in (1, 2)
            ]
            status_codes = [future.result(timeout=30) for future in futures]

        self.assertEqual(status_codes.count(201), 1)
        self.assertEqual(status_codes.count(400), 1)

        self.assertEqual(
            Appointment.objects.filter(
                doctor=self.doctor,
                start_time=self.start_time,
                status="booked",
            ).count(),
            1,
        )
