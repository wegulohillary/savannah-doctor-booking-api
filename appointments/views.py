
from datetime import datetime, timedelta

from django.db.models import Q
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView

from appointments.models import (
    Appointment,
    Doctor,
    WorkingHours,
)
from appointments.serializers import (
    AppointmentCreateSerializer,
    AppointmentSerializer,
    DoctorSerializer,
    RescheduleSerializer,
)
from appointments.services.booking import (
    BookingError,
    BookingTooSoon,
    InvalidBooking,
    SlotUnavailable,
    create_appointment,
    cancel_appointment,
    reschedule_appointment,
)


class HealthView(APIView):
    def get(self, request):
        return Response(
            {
                "status": "ok",
                "service": "savannah-doctor-booking-api",
                "message": "API is running",
            },
            status=status.HTTP_200_OK,
        )


class BookingAPIException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Unable to process the booking."
    default_code = "booking_error"


def booking_error_response(exc):
    if isinstance(exc, BookingTooSoon):
        code = status.HTTP_400_BAD_REQUEST
    elif isinstance(exc, SlotUnavailable):
        code = status.HTTP_400_BAD_REQUEST
    elif isinstance(exc, InvalidBooking):
        code = status.HTTP_400_BAD_REQUEST
    else:
        code = status.HTTP_400_BAD_REQUEST

    return Response(
        {"error": str(exc)},
        status=code,
    )


class DoctorListView(generics.ListAPIView):
    serializer_class = DoctorSerializer

    def get_queryset(self):
        return Doctor.objects.filter(is_active=True).order_by("name")


class DoctorAvailabilityView(APIView):
    def get(self, request, doctor_id):
        date_string = request.query_params.get("date")

        if not date_string:
            return Response(
                {"error": "The date query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            requested_date = datetime.strptime(
                date_string,
                "%Y-%m-%d",
            ).date()
        except ValueError:
            return Response(
                {"error": "Date must use YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        doctor = Doctor.objects.filter(
            pk=doctor_id,
            is_active=True,
        ).first()

        if not doctor:
            return Response(
                {"error": "Doctor not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        weekday = requested_date.weekday()

        working_hours = WorkingHours.objects.filter(
            doctor=doctor,
            weekday=weekday,
        ).first()

        if not working_hours:
            return Response({
                "doctor_id": doctor.id,
                "date": date_string,
                "available_slots": [],
            })

        local_timezone = timezone.get_current_timezone()

        start_datetime = timezone.make_aware(
            datetime.combine(
                requested_date,
                working_hours.start_time,
            ),
            local_timezone,
        )

        end_datetime = timezone.make_aware(
            datetime.combine(
                requested_date,
                working_hours.end_time,
            ),
            local_timezone,
        )

        appointments = Appointment.objects.filter(
            doctor=doctor,
            status=Appointment.Status.BOOKED,
            start_time__lt=end_datetime,
            end_time__gt=start_datetime,
        ).order_by("start_time")

        available_slots = []
        current_time = timezone.now()
        earliest_booking_time = current_time + timedelta(hours=1)

        while current_time is not None and start_datetime + timedelta(minutes=30) <= end_datetime:
            slot_end = start_datetime + timedelta(minutes=30)

            # Exclude slots that are too close to now.
            if start_datetime >= earliest_booking_time:
                # Exclude slots overlapping existing appointments.
                is_booked = appointments.filter(
                    start_time__lt=slot_end,
                    end_time__gt=start_datetime,
                ).exists()

                if not is_booked:
                    available_slots.append({
                        "start_time": start_datetime.isoformat(),
                        "end_time": slot_end.isoformat(),
                    })

            start_datetime = slot_end

        return Response({
            "doctor_id": doctor.id,
            "doctor_name": doctor.name,
            "date": date_string,
            "available_slots": available_slots,
        })


class AppointmentCreateView(APIView):
    def post(self, request):
        serializer = AppointmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            appointment = create_appointment(
                doctor_id=serializer.validated_data["doctor_id"],
                patient_name=serializer.validated_data["patient_name"],
                patient_email=serializer.validated_data["patient_email"],
                patient_phone=serializer.validated_data["patient_phone"],
                start_time=serializer.validated_data["start_time"],
            )
        except BookingError as exc:
            return booking_error_response(exc)

        return Response(
            AppointmentSerializer(appointment).data,
            status=status.HTTP_201_CREATED,
        )


class UpcomingAppointmentsView(generics.ListAPIView):
    serializer_class = AppointmentSerializer

    def get_queryset(self):
        return (
            Appointment.objects
            .filter(
                status=Appointment.Status.BOOKED,
                start_time__gte=timezone.now(),
            )
            .select_related("doctor", "patient")
            .order_by("start_time")
        )


class AppointmentDetailView(generics.RetrieveAPIView):
    serializer_class = AppointmentSerializer

    def get_queryset(self):
        return Appointment.objects.select_related(
            "doctor",
        "patient",
    )


class AppointmentCancelView(APIView):
    def patch(self, request, appointment_id):
        try:
            appointment = cancel_appointment(appointment_id)
        except BookingError as exc:
            return booking_error_response(exc)

        return Response(
            AppointmentSerializer(appointment).data,
            status=status.HTTP_200_OK,
        )


class AppointmentRescheduleView(APIView):
    def patch(self, request, appointment_id):
        serializer = RescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            appointment = reschedule_appointment(
                appointment_id=appointment_id,
                new_start_time=serializer.validated_data["start_time"],
            )
        except BookingError as exc:
            return booking_error_response(exc)

        return Response(
            AppointmentSerializer(appointment).data,
            status=status.HTTP_200_OK,
        )
