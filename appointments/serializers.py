
from rest_framework import serializers

from appointments.models import Appointment, Doctor


class DoctorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Doctor
        fields = ["id", "name", "specialty"]


class AppointmentCreateSerializer(serializers.Serializer):
    doctor_id = serializers.IntegerField(min_value=1)
    patient_name = serializers.CharField(max_length=150)
    patient_email = serializers.EmailField()
    patient_phone = serializers.CharField(max_length=30)
    start_time = serializers.DateTimeField()

    def validate_patient_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Patient name cannot be empty."
            )

        return value

    def validate_patient_phone(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Patient phone number cannot be empty."
            )

        return value


class RescheduleSerializer(serializers.Serializer):
    start_time = serializers.DateTimeField()


class AppointmentSerializer(serializers.ModelSerializer):
    doctor_name = serializers.CharField(
        source="doctor.name",
        read_only=True,
    )
    doctor_specialty = serializers.CharField(
        source="doctor.specialty",
        read_only=True,
    )
    patient_name = serializers.CharField(
        source="patient.full_name",
        read_only=True,
    )

    class Meta:
        model = Appointment
        fields = [
            "id",
            "doctor",
            "doctor_name",
            "doctor_specialty",
            "patient",
            "patient_name",
            "start_time",
            "end_time",
            "status",
            "created_at",
        ]
        read_only_fields = fields
