
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from appointments.models import (
    Appointment,
    Doctor,
    Patient,
    WorkingHours,
)

SLOT_DURATION = timedelta(minutes=30)
MINIMUM_BOOKING_NOTICE = timedelta(hours=1)


class BookingError(Exception):
    """Base exception for booking-related errors."""


class SlotUnavailable(BookingError):
    """The requested slot cannot be booked."""


class BookingTooSoon(BookingError):
    """The appointment is too close to the current time."""


class InvalidBooking(BookingError):
    """The requested appointment data is invalid."""


def validate_booking_time(start_time):
    if timezone.is_naive(start_time):
        raise InvalidBooking(
            "Appointment start time must include a timezone."
        )

    if start_time < timezone.now() + MINIMUM_BOOKING_NOTICE:
        raise BookingTooSoon(
            "Appointments must be booked at least "
            "one hour in advance."
        )


def validate_doctor_slot(doctor, start_time, end_time):
    if not doctor.is_active:
        raise SlotUnavailable("This doctor is not available.")

    if start_time.date() != end_time.date():
        raise InvalidBooking(
            "Appointments must start and end on the same day."
        )

    if end_time - start_time != SLOT_DURATION:
        raise InvalidBooking(
            "Appointments must last exactly 30 minutes."
        )

    if start_time.second != 0 or start_time.microsecond != 0:
        raise InvalidBooking(
            "Appointment times must be on the minute."
        )

    local_start = timezone.localtime(start_time)
    local_end = timezone.localtime(end_time)

    if local_start.date() != local_end.date():
        raise InvalidBooking(
            "Appointments must start and end on the same day."
        )

    working_hours = WorkingHours.objects.filter(
        doctor=doctor,
        weekday=local_start.weekday(),
    ).first()

    if not working_hours:
        raise SlotUnavailable(
            "The doctor does not work on this day."
        )

    if (
        local_start.time() < working_hours.start_time
        or local_end.time() > working_hours.end_time
    ):
        raise SlotUnavailable(
            "The requested time is outside the doctor's "
            "working hours."
        )

    minutes_from_open = (
        local_start.hour * 60
        + local_start.minute
        - (
            working_hours.start_time.hour * 60
            + working_hours.start_time.minute
        )
    )

    if minutes_from_open < 0 or minutes_from_open % 30 != 0:
        raise InvalidBooking(
            "Please select a valid 30-minute appointment slot."
        )


def ensure_slot_is_free(
    doctor,
    start_time,
    end_time,
    exclude_appointment_id=None,
):
    overlapping = Appointment.objects.filter(
        doctor=doctor,
        status=Appointment.Status.BOOKED,
        start_time__lt=end_time,
        end_time__gt=start_time,
    )

    if exclude_appointment_id is not None:
        overlapping = overlapping.exclude(
            pk=exclude_appointment_id
        )

    if overlapping.exists():
        raise SlotUnavailable(
            "This appointment slot is already booked."
        )


@transaction.atomic
def create_appointment(
    *,
    doctor_id,
    patient_name,
    patient_email,
    patient_phone,
    start_time,
):
    try:
        doctor = Doctor.objects.select_for_update().get(
            pk=doctor_id
        )
    except Doctor.DoesNotExist:
        raise InvalidBooking("The selected doctor does not exist.")

    validate_booking_time(start_time)

    end_time = start_time + SLOT_DURATION

    validate_doctor_slot(doctor, start_time, end_time)

    ensure_slot_is_free(doctor, start_time, end_time)

    patient = Patient.objects.create(
        full_name=patient_name,
        email=patient_email,
        phone_number=patient_phone,
    )

    try:
        appointment = Appointment.objects.create(
            doctor=doctor,
            patient=patient,
            start_time=start_time,
            end_time=end_time,
            status=Appointment.Status.BOOKED,
        )
    except IntegrityError:
        raise SlotUnavailable(
            "This appointment slot was just booked. "
        "Please select another time."
    )

    return appointment


@transaction.atomic
def cancel_appointment(appointment_id):
    try:
        appointment = (
            Appointment.objects.select_for_update()
            .get(pk=appointment_id)
        )
    except Appointment.DoesNotExist:
        raise InvalidBooking("Appointment not found.")

    if appointment.status == Appointment.Status.CANCELLED:
        raise InvalidBooking("This appointment is already cancelled.")

    appointment.status = Appointment.Status.CANCELLED
    appointment.save(update_fields=["status", "updated_at"])

    return appointment


@transaction.atomic
def reschedule_appointment(
    *,
    appointment_id,
    new_start_time,
):
    try:
        appointment = (
            Appointment.objects.select_for_update()
            .get(pk=appointment_id)
        )
    except Appointment.DoesNotExist:
        raise InvalidBooking("Appointment not found.")

    if appointment.status != Appointment.Status.BOOKED:
        raise InvalidBooking(
            "Only booked appointments can be rescheduled."
        )

    validate_booking_time(new_start_time)

    doctor = Doctor.objects.select_for_update().get(
        pk=appointment.doctor_id
    )

    new_end_time = new_start_time + SLOT_DURATION

    validate_doctor_slot(
        doctor,
        new_start_time,
        new_end_time,
    )

    ensure_slot_is_free(
        doctor,
        new_start_time,
        new_end_time,
        exclude_appointment_id=appointment.id,
    )

    appointment.start_time = new_start_time
    appointment.end_time = new_end_time

    try:
        appointment.save(
            update_fields=[
                "start_time",
                "end_time",
                "updated_at",
            ]
        )
    except IntegrityError:
        raise SlotUnavailable(
            "This appointment slot was just booked. "
            "Please select another time."
        )

    return appointment
