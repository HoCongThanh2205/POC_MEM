from datetime import date

from django.db import models
from django.utils import timezone


class Department(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)

    def __str__(self):
        return f"{self.code} - {self.name}"


class Location(models.Model):
    name = models.CharField(max_length=128)

    def __str__(self):
        return self.name


class Vendor(models.Model):
    name = models.CharField(max_length=128)

    def __str__(self):
        return self.name


class Asset(models.Model):
    class AssetType(models.TextChoices):
        MAIN = "MAIN", "Main"
        ACCESSORY = "ACCESSORY", "Accessory"
        TOOL = "TOOL", "Tool"

    class OperationalStatus(models.TextChoices):
        IN_USE = "IN_USE", "In Use"
        STANDBY = "STANDBY", "Standby"
        BROKEN = "BROKEN", "Broken"

    asset_code = models.CharField(max_length=64, unique=True)
    standardized_name = models.CharField(max_length=255)
    barcode = models.CharField(max_length=128, blank=True, unique=True, null=True)
    asset_type = models.CharField(max_length=16, choices=AssetType.choices, default=AssetType.MAIN)

    category_group = models.CharField(max_length=128)
    risk_class = models.CharField(max_length=16, blank=True)
    manufacturer = models.CharField(max_length=128, blank=True)
    model_name = models.CharField(max_length=128, blank=True)
    year_of_manufacture = models.PositiveSmallIntegerField(null=True, blank=True)

    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets",
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets",
    )
    pic_owner = models.CharField(max_length=128, blank=True)
    ops_note = models.CharField(max_length=255, blank=True)

    is_disabled = models.BooleanField(default=False)
    operational_status = models.CharField(
        max_length=20,
        choices=OperationalStatus.choices,
        default=OperationalStatus.IN_USE,
    )

    inspection_required = models.BooleanField(default=True)
    inspection_last_date = models.DateField(null=True, blank=True)
    inspection_expiry_date = models.DateField(null=True, blank=True)

    pm_required = models.BooleanField(default=True)
    pm_last_date = models.DateField(null=True, blank=True)
    pm_next_due_date = models.DateField(null=True, blank=True)

    commissioning_date = models.DateField(null=True, blank=True)
    useful_life_years = models.PositiveSmallIntegerField(default=8)
    expected_eol_at = models.DateField(null=True, blank=True)

    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets",
    )
    warranty_start_date = models.DateField(null=True, blank=True)
    warranty_end_date = models.DateField(null=True, blank=True)
    service_contract_id = models.CharField(max_length=128, blank=True)
    contract_end_date = models.DateField(null=True, blank=True)

    serial_number = models.CharField(max_length=128, blank=True)
    imei = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "asset_code"]

    def __str__(self):
        return self.asset_code

    @property
    def effective_operational_status(self) -> str:
        if self.is_disabled:
            return "DISABLED"
        return self.operational_status

    def _days_remaining(self, target_date):
        if not target_date:
            return None
        return (target_date - timezone.localdate()).days

    def inspection_status(self, warning_days=30):
        if not self.inspection_required:
            return "NOT_REQUIRED", None
        days = self._days_remaining(self.inspection_expiry_date)
        if days is None:
            return "MISSING_DATE", None
        if days < 0:
            return "OVERDUE", days
        if days <= warning_days:
            return "DUE_SOON", days
        return "VALID", days

    def pm_status(self, warning_days=30):
        if not self.pm_required:
            return "NOT_REQUIRED", None
        days = self._days_remaining(self.pm_next_due_date)
        if days is None:
            return "MISSING_DATE", None
        if days < 0:
            return "OVERDUE", days
        if days <= warning_days:
            return "DUE_SOON", days
        return "VALID", days

    def eol_date(self):
        if self.expected_eol_at:
            return self.expected_eol_at
        if not self.commissioning_date:
            return None
        target_year = self.commissioning_date.year + self.useful_life_years
        try:
            return self.commissioning_date.replace(year=target_year)
        except ValueError:
            return self.commissioning_date.replace(month=2, day=28, year=target_year)

    def eol_status(self, warning_days=60):
        eol = self.eol_date()
        days = self._days_remaining(eol)
        if days is None:
            return "MISSING_DATE", None, None
        if days < 0:
            return "EXPIRED", days, eol
        if days <= warning_days:
            return "DUE_SOON", days, eol
        return "WITHIN_LIFE", days, eol


class Incident(models.Model):
    class Status(models.TextChoices):
        REPORTED = "REPORTED", "Reported"
        CONFIRMED = "CONFIRMED", "Confirmed"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="incidents")
    incident_code = models.CharField(max_length=64)
    reported_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    symptom = models.CharField(max_length=255)
    priority = models.CharField(max_length=16, default="MEDIUM")
    root_cause = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.REPORTED)

    class Meta:
        ordering = ["-reported_at"]


class WorkOrder(models.Model):
    class Type(models.TextChoices):
        PM = "PM", "PM"
        REPAIR = "REPAIR", "Repair"
        CALIBRATION = "CALIBRATION", "Calibration"
        INSPECTION = "INSPECTION", "Inspection"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        OVERDUE = "OVERDUE", "Overdue"

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="work_orders")
    wo_code = models.CharField(max_length=64)
    wo_type = models.CharField(max_length=16, choices=Type.choices)
    title = models.CharField(max_length=255, blank=True)
    technician = models.CharField(max_length=128, blank=True)
    scheduled_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    completed_date = models.DateField(null=True, blank=True)
    checklist_summary = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)

    class Meta:
        ordering = ["-id"]


class ComplianceRecord(models.Model):
    class Type(models.TextChoices):
        CALIBRATION = "CALIBRATION", "Calibration"
        VERIFICATION = "VERIFICATION", "Verification"
        SAFETY_TEST = "SAFETY_TEST", "Safety Test"
        INSPECTION = "INSPECTION", "Inspection"

    class Result(models.TextChoices):
        PASS = "PASS", "Pass"
        FAIL = "FAIL", "Fail"

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="compliance_records")
    record_code = models.CharField(max_length=64)
    compliance_type = models.CharField(max_length=16, choices=Type.choices)
    performed_by = models.CharField(max_length=32, default="INTERNAL")
    performed_at = models.DateField()
    next_due_at = models.DateField(null=True, blank=True)
    result = models.CharField(max_length=8, choices=Result.choices, default=Result.PASS)
    certificate_name = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-performed_at"]


class HandoverRecord(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="handovers")
    doc_id = models.CharField(max_length=64)
    from_location = models.CharField(max_length=255)
    to_location = models.CharField(max_length=255)
    custodian_after = models.CharField(max_length=128)
    handover_date = models.DateField()
    accessories_summary = models.CharField(max_length=255, blank=True)
    signed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-handover_date"]


class MovementRecord(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="movements")
    moved_at = models.DateTimeField()
    from_location = models.CharField(max_length=255)
    to_location = models.CharField(max_length=255)
    action_by = models.CharField(max_length=128)
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-moved_at"]


class Accessory(models.Model):
    class Status(models.TextChoices):
        OK = "OK", "OK"
        MISSING = "MISSING", "Missing"
        DAMAGED = "DAMAGED", "Damaged"

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="accessories")
    accessory_name = models.CharField(max_length=128)
    code_or_serial = models.CharField(max_length=128, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OK)
    mandatory = models.BooleanField(default=False)
    last_verified_date = models.DateField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)


class PartConsumption(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="part_consumptions")
    consumed_at = models.DateField()
    wo_code = models.CharField(max_length=64, blank=True)
    part_code = models.CharField(max_length=64)
    part_name = models.CharField(max_length=128)
    quantity = models.PositiveIntegerField(default=1)
    batch_info = models.CharField(max_length=128, blank=True)
    issued_store = models.CharField(max_length=128, blank=True)
    cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ["-consumed_at"]


class AssetDocument(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="documents")
    doc_type = models.CharField(max_length=32)
    file_name = models.CharField(max_length=255)
    related_to = models.CharField(max_length=64, blank=True)
    updated_at = models.DateField(default=date.today)

    class Meta:
        ordering = ["-updated_at"]


class AuditLog(models.Model):
    entity_type = models.CharField(max_length=32)
    entity_id = models.PositiveBigIntegerField()
    action = models.CharField(max_length=64)
    field_name = models.CharField(max_length=64, blank=True)
    before_value = models.TextField(blank=True)
    after_value = models.TextField(blank=True)
    reason = models.CharField(max_length=128, blank=True)
    note = models.TextField(blank=True)
    actor = models.CharField(max_length=128, blank=True)
    acted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-acted_at"]

    def __str__(self):
        return f"{self.entity_type}:{self.entity_id}:{self.action}"
